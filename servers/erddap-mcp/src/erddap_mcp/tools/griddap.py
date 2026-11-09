"""Gridded data access tools (griddap)."""

from __future__ import annotations

from typing import Literal
import json
from collections import OrderedDict

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ERDDAPClient
from ..server import mcp
from ..utils import (
    build_griddap_query,
    cap_rows,
    format_erddap_table,
    handle_erddap_error,
    parse_erddap_json,
)


def _get_client(ctx: Context) -> ERDDAPClient:
    return ctx.request_context.lifespan_context["erddap_client"]


def _parse_dimensions_from_info(info_rows: list[dict]) -> list[str]:
    """Extract dimension names in order from dataset info rows."""
    dimensions = []
    for row in info_rows:
        if row.get("Row Type") == "dimension":
            dim_name = row.get("Variable Name", "")
            if dim_name and dim_name not in dimensions:
                dimensions.append(dim_name)
    return dimensions


def _get_data_variables_from_info(info_rows: list[dict]) -> list[str]:
    """Extract non-dimension variable names from dataset info rows."""
    dimensions = set()
    variables = []
    for row in info_rows:
        if row.get("Row Type") == "dimension":
            dimensions.add(row.get("Variable Name", ""))

    for row in info_rows:
        if row.get("Row Type") == "variable":
            var_name = row.get("Variable Name", "")
            if var_name and var_name not in dimensions and var_name not in variables:
                variables.append(var_name)
    return variables


def _units_from_info(info_rows: list[dict], names: list[str]) -> dict[str, str | None]:
    """Each variable's ``units`` attribute from the dataset info rows (None if absent).

    Only data variables are reported: ERDDAP's .json writes the time dimension as
    ISO 8601 strings, so the metadata's time units would not describe the values.
    """
    units: dict[str, str | None] = {name: None for name in names}
    for row in info_rows:
        name = row.get("Variable Name", "")
        if (
            row.get("Row Type") == "attribute"
            and row.get("Attribute Name") == "units"
            and name in units
        ):
            value = str(row.get("Value", "")).strip()
            units[name] = value or None
    return units


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def erddap_get_griddap_data(
    ctx: Context,
    server_url: str,
    dataset_id: str,
    variables: list[str] | None = None,
    time_range: list[str] | None = None,
    latitude_range: list[float] | None = None,
    longitude_range: list[float] | None = None,
    depth_range: list[float] | None = None,
    stride: int = 1,
    response_format: Literal["markdown", "json"] = "markdown",
    max_records: int = 2000,
) -> str:
    """Retrieve gridded data from an ERDDAP griddap dataset with dimension subsetting.

    Args:
        server_url: ERDDAP server URL (e.g., 'https://coastwatch.pfeg.noaa.gov/erddap').
        dataset_id: ERDDAP dataset identifier (e.g., 'erdMH1chlamday').
        variables: List of variable names to retrieve (default: first data variable).
        time_range: Time range as [start, stop] (e.g., ['2024-01-01T00:00:00Z', '2024-01-31T00:00:00Z']). Use same value for single time step.
        latitude_range: Latitude range as [min, max] (e.g., [36.0, 38.0]).
        longitude_range: Longitude range as [min, max] (e.g., [-123.0, -121.0]).
        depth_range: Depth/altitude range as [min, max] (optional, for datasets with depth dimension).
        stride: Step size for subsetting (default 1). Increase to reduce data volume.
        response_format: Output format — 'markdown' (default) or 'json'.
        max_records: Cap on JSON rows returned (default 2000). The first
            max_records grid points are kept and the JSON flags any truncation.
            (Markdown is already capped at 100 rows.)
    """
    try:
        client = _get_client(ctx)

        # Step 1: Query dataset info to get dimension order
        info_data = await client.get_info(server_url=server_url, dataset_id=dataset_id)
        info_rows = parse_erddap_json(info_data)

        dim_names = _parse_dimensions_from_info(info_rows)

        if not dim_names:
            return f"Could not determine dimensions for dataset '{dataset_id}'. Use erddap_get_dataset_info for details."

        # Determine variables to request
        if not variables:
            data_vars = _get_data_variables_from_info(info_rows)
            if not data_vars:
                return f"No data variables found for dataset '{dataset_id}'."
            variables = [data_vars[0]]

        # Step 2: Build dimension constraints based on what the dataset has
        # Map user inputs to dimension names (common ERDDAP dimension names)
        dim_map: dict[str, tuple[str, str] | tuple[str, str, str] | None] = {}
        time_dims = {"time"}
        lat_dims = {"latitude", "lat", "y"}
        lon_dims = {"longitude", "lon", "x"}
        depth_dims = {"depth", "altitude", "z", "lev", "level"}

        for dim in dim_names:
            dim_lower = dim.lower()
            if dim_lower in time_dims or "time" in dim_lower:
                if time_range and len(time_range) >= 2:
                    dim_map[dim] = (time_range[0], time_range[1])
                elif time_range and len(time_range) == 1:
                    dim_map[dim] = (time_range[0], time_range[0])
                else:
                    dim_map[dim] = ("last", "last")
            elif dim_lower in lat_dims or "lat" in dim_lower:
                if latitude_range and len(latitude_range) >= 2:
                    dim_map[dim] = (str(latitude_range[0]), str(latitude_range[1]))
                elif latitude_range and len(latitude_range) == 1:
                    dim_map[dim] = (str(latitude_range[0]), str(latitude_range[0]))
                # If no lat range provided, omit to get all
            elif dim_lower in lon_dims or "lon" in dim_lower:
                if longitude_range and len(longitude_range) >= 2:
                    dim_map[dim] = (str(longitude_range[0]), str(longitude_range[1]))
                elif longitude_range and len(longitude_range) == 1:
                    dim_map[dim] = (str(longitude_range[0]), str(longitude_range[0]))
            elif dim_lower in depth_dims or "depth" in dim_lower or "alt" in dim_lower:
                if depth_range and len(depth_range) >= 2:
                    dim_map[dim] = (str(depth_range[0]), str(depth_range[1]))
                elif depth_range and len(depth_range) == 1:
                    dim_map[dim] = (str(depth_range[0]), str(depth_range[0]))

        # Apply stride
        if stride > 1:
            new_dim_map: dict[str, tuple[str, str] | tuple[str, str, str]] = {}
            for dim, val in dim_map.items():
                if val and len(val) == 2:
                    new_dim_map[dim] = (val[0], str(stride), val[1])
                else:
                    new_dim_map[dim] = val
            dim_map = new_dim_map

        # Build ordered dimensions dict preserving dataset dimension order
        # ERDDAP requires ALL dimensions in bracket notation — default unmatched ones to last value
        ordered_dims: OrderedDict[str, tuple] = OrderedDict()
        for dim in dim_names:
            if dim in dim_map and dim_map[dim] is not None:
                ordered_dims[dim] = dim_map[dim]
            else:
                # Default unmatched dimensions to last available value
                ordered_dims[dim] = ("last", "last")

        # Warn about potentially large requests
        warnings: list[str] = []
        if stride == 1:
            # Check if spatial range is large
            if latitude_range and len(latitude_range) >= 2:
                lat_span = abs(latitude_range[1] - latitude_range[0])
                if lat_span > 10:
                    warnings.append(
                        f"Large latitude range ({lat_span}\u00b0). Consider increasing stride or narrowing the range."
                    )
            if longitude_range and len(longitude_range) >= 2:
                lon_span = abs(longitude_range[1] - longitude_range[0])
                if lon_span > 10:
                    warnings.append(
                        f"Large longitude range ({lon_span}\u00b0). Consider increasing stride or narrowing the range."
                    )

        # Build query for each variable
        query_parts = []
        for var in variables:
            query_parts.append(build_griddap_query(var, ordered_dims))
        query = ",".join(query_parts)

        data = await client.get_griddap(
            server_url=server_url,
            dataset_id=dataset_id,
            query=query,
        )

        rows = parse_erddap_json(data)

        if response_format == "json":
            kept, env = cap_rows(rows, max_records)
            units = _units_from_info(info_rows, variables)
            result = {
                "server_url": server_url,
                "dataset_id": dataset_id,
                "dimensions": dim_names,
                "variables": variables,
                "units": units,
                "units_missing": [name for name, u in units.items() if u is None],
                **env,
                "data": kept,
            }
            if warnings:
                result["warnings"] = warnings
            return json.dumps(result, indent=2)

        # Markdown output
        lines: list[str] = []
        if warnings:
            for w in warnings:
                lines.append(f"**Warning**: {w}")
            lines.append("")

        table = data.get("table", {})
        columns = table.get("columnNames", [])
        units = table.get("columnUnits", [])

        display_columns = []
        for i, col in enumerate(columns):
            unit = units[i] if i < len(units) and units[i] else ""
            if unit and unit != "null":
                display_columns.append(f"{col} ({unit})")
            else:
                display_columns.append(col)

        meta = [f"Server: {server_url}", f"Dimensions: {', '.join(dim_names)}"]
        if stride > 1:
            meta.append(f"Stride: {stride}")

        table_output = format_erddap_table(
            rows,
            columns=display_columns if display_columns else None,
            title=f"Griddap Data \u2014 {dataset_id}",
            metadata_lines=meta,
            count_label="grid points",
            max_rows=100,
        )

        lines.append(table_output)
        return "\n".join(lines)

    except Exception as e:
        return handle_erddap_error(e, server_url)
