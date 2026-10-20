"""Unit tests for ERDDAP utility functions."""

from collections import OrderedDict

from erddap_mcp.utils import (
    build_griddap_query,
    build_tabledap_query,
    cap_rows,
    format_erddap_table,
    handle_erddap_error,
    parse_erddap_json,
)


# --- parse_erddap_json ---


class TestParseErddapJson:
    def test_basic_parsing(self):
        data = {
            "table": {
                "columnNames": ["time", "sst"],
                "rows": [
                    ["2024-01-01T00:00:00Z", 12.5],
                    ["2024-01-02T00:00:00Z", 13.0],
                ],
            }
        }
        rows = parse_erddap_json(data)
        assert len(rows) == 2
        assert rows[0] == {"time": "2024-01-01T00:00:00Z", "sst": 12.5}
        assert rows[1] == {"time": "2024-01-02T00:00:00Z", "sst": 13.0}

    def test_empty_rows(self):
        data = {"table": {"columnNames": ["time", "sst"], "rows": []}}
        assert parse_erddap_json(data) == []

    def test_missing_table(self):
        assert parse_erddap_json({}) == []

    def test_missing_columns(self):
        data = {"table": {"rows": [["a", 1]]}}
        rows = parse_erddap_json(data)
        assert rows == [{}]

    def test_single_column(self):
        data = {"table": {"columnNames": ["id"], "rows": [["abc"], ["def"]]}}
        rows = parse_erddap_json(data)
        assert rows == [{"id": "abc"}, {"id": "def"}]


# --- build_tabledap_query ---


class TestBuildTabledapQuery:
    def test_variables_only(self):
        q = build_tabledap_query(variables=["time", "sst", "latitude"])
        assert q == "time,sst,latitude"

    def test_numeric_constraints(self):
        q = build_tabledap_query(constraints={"latitude>=": 37.0, "latitude<=": 38.0})
        assert "latitude>=37.0" in q
        assert "latitude<=38.0" in q

    def test_integer_constraints(self):
        q = build_tabledap_query(constraints={"depth>=": 0, "depth<=": 100})
        assert "depth>=0" in q
        assert "depth<=100" in q

    def test_string_equality_constraint_quoted(self):
        q = build_tabledap_query(constraints={"station=": "46013"})
        assert 'station="46013"' in q

    def test_date_range_constraint_quoted(self):
        q = build_tabledap_query(constraints={"time>=": "2024-01-01T00:00:00Z"})
        assert 'time>="2024-01-01T00:00:00Z"' in q

    def test_numeric_string_with_range_op_not_quoted(self):
        q = build_tabledap_query(constraints={"latitude>=": "37.5"})
        assert "latitude>=37.5" in q
        assert '"' not in q

    def test_combined_variables_and_constraints(self):
        q = build_tabledap_query(
            variables=["time", "sst"],
            constraints={"time>=": "2024-01-01"},
        )
        parts = q.split("&")
        assert parts[0] == "time,sst"
        assert 'time>="2024-01-01"' in parts[1]

    def test_limit(self):
        q = build_tabledap_query(variables=["sst"], limit=100)
        assert "sst" in q
        assert 'orderByLimit("100")' in q

    def test_no_args_returns_empty(self):
        q = build_tabledap_query()
        assert q == ""

    def test_regex_constraint(self):
        q = build_tabledap_query(constraints={"station=~": "46.*"})
        assert 'station=~"46.*"' in q


# --- build_griddap_query ---


class TestBuildGriddapQuery:
    def test_single_point(self):
        dims = OrderedDict(
            [
                ("time", ("2024-01-15T00:00:00Z", "2024-01-15T00:00:00Z")),
                ("latitude", ("37.0", "37.0")),
                ("longitude", ("-122.0", "-122.0")),
            ]
        )
        q = build_griddap_query("sst", dims)
        assert q == "sst[(2024-01-15T00:00:00Z)][(37.0)][(-122.0)]"

    def test_range(self):
        dims = OrderedDict(
            [
                ("time", ("last", "last")),
                ("latitude", ("36.0", "38.0")),
                ("longitude", ("-123.0", "-121.0")),
            ]
        )
        q = build_griddap_query("chlorophyll", dims)
        assert q == "chlorophyll[(last)][(36.0):(38.0)][(-123.0):(-121.0)]"

    def test_with_stride(self):
        dims = OrderedDict(
            [
                ("time", ("last", "last")),
                ("latitude", ("30.0", "2", "40.0")),
                ("longitude", ("-130.0", "2", "-120.0")),
            ]
        )
        q = build_griddap_query("sst", dims)
        assert q == "sst[(last)][(30.0):(2):(40.0)][(-130.0):(2):(-120.0)]"

    def test_four_dimensions(self):
        dims = OrderedDict(
            [
                ("time", ("last", "last")),
                ("depth", ("0.0", "0.0")),
                ("latitude", ("36.0", "38.0")),
                ("longitude", ("-123.0", "-121.0")),
            ]
        )
        q = build_griddap_query("temp", dims)
        assert q == "temp[(last)][(0.0)][(36.0):(38.0)][(-123.0):(-121.0)]"

    def test_empty_dimensions(self):
        q = build_griddap_query("sst", OrderedDict())
        assert q == "sst"


# --- format_erddap_table ---


class TestFormatErddapTable:
    def test_basic_table(self):
        rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = format_erddap_table(rows, title="Test")
        assert "## Test" in result
        assert "| a | b |" in result
        assert "| 1 | 2 |" in result
        assert "*2 records returned.*" in result

    def test_empty_rows(self):
        result = format_erddap_table([], title="Empty")
        assert "No records found." in result

    def test_custom_columns(self):
        rows = [{"x": 10, "y": 20}]
        result = format_erddap_table(rows, columns=["x (m)", "y (m)"])
        assert "| x (m) | y (m) |" in result

    def test_max_rows_truncation(self):
        rows = [{"v": i} for i in range(100)]
        result = format_erddap_table(rows, max_rows=10, count_label="points")
        assert "Showing 10 of 100 points" in result

    def test_metadata_lines(self):
        rows = [{"a": 1}]
        result = format_erddap_table(
            rows, metadata_lines=["Server: test", "Mode: grid"]
        )
        assert "**Server: test**" in result
        assert "**Mode: grid**" in result

    def test_long_cell_truncated(self):
        rows = [{"text": "x" * 200}]
        result = format_erddap_table(rows)
        assert "..." in result
        # Cell shouldn't exceed ~100 chars
        for line in result.split("\n"):
            if "xxx" in line:
                cell = line.split("|")[1].strip()
                assert len(cell) <= 100


# --- handle_erddap_error ---


class TestHandleErddapError:
    def test_generic_exception(self):
        result = handle_erddap_error(
            ValueError("bad value"), "https://example.com/erddap"
        )
        assert "Unexpected error" in result
        assert "bad value" in result

    def test_json_error_hint(self):
        result = handle_erddap_error(
            ValueError("failed to decode json"), "https://example.com/erddap"
        )
        assert "parsing ERDDAP response" in result

    def test_connect_error(self):
        import httpx

        err = httpx.ConnectError("connection refused")
        result = handle_erddap_error(err, "https://example.com/erddap")
        assert "Could not connect" in result
        assert "example.com" in result

    def test_timeout_error(self):
        import httpx

        err = httpx.ReadTimeout("timed out")
        result = handle_erddap_error(err, "https://example.com/erddap")
        assert "timed out" in result.lower()

    def test_untrusted_certificate(self):
        """A certificate-verification failure is not reported as an outage."""
        import ssl

        import httpx

        cause = ssl.SSLCertVerificationError(1, "certificate verify failed")
        cause.verify_message = "unable to get local issuer certificate"
        try:
            raise httpx.ConnectError("certificate verify failed") from cause
        except httpx.ConnectError as err:
            result = handle_erddap_error(err, "https://example.com/erddap")
        assert "Could not verify the TLS certificate" in result
        assert "example.com" in result
        assert "unable to get local issuer certificate" in result
        assert "certifi" in result
        assert "may be down" not in result


# --- cap_rows ---


class TestCapRows:
    def test_under_cap_untouched(self):
        """At or below the cap nothing is trimmed; counts agree, no hint."""
        rows = [{"i": n} for n in range(10)]
        kept, env = cap_rows(rows, 2000)
        assert kept == rows
        assert env["truncated"] is False
        assert env["record_count"] == 10
        assert env["total"] == 10
        assert "hint" not in env

    def test_over_cap_keeps_head(self):
        """Over the cap, the first max_records rows are kept (head), with a hint."""
        rows = [{"i": n} for n in range(2500)]
        kept, env = cap_rows(rows, 2000)
        assert len(kept) == 2000
        assert kept[0]["i"] == 0
        assert kept[-1]["i"] == 1999
        assert env["truncated"] is True
        assert env["record_count"] == 2000
        assert env["total"] == 2500
        assert "first 2000 of 2500 rows" in env["hint"]
