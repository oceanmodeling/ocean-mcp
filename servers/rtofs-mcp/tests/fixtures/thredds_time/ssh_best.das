Attributes {
    tau {
        String units "hours since analysis";
        String long_name "Tau";
        String time_origin "2026-11-06 12:00:00";
        Int32 NAVO_code 56;
    }
    surf_el {
        String units "m";
        String long_name "Water Surface Elevation";
        String standard_name "sea_surface_elevation";
        Int32 NAVO_code 32;
        Float32 actual_range -5.94, 4.7130003;
        String coordinates "time_run time lat lon ";
    }
    time_offset {
        String long_name "offset hour from start of run for coordinate = time";
        String standard_name "forecast_period";
        String calendar "proleptic_gregorian";
        String units "hours since 2026-10-30T12:00:00Z";
        Float64 missing_value NaN;
    }
    lat {
        String units "degrees_north";
        String long_name "Latitude";
        String standard_name "latitude";
        String point_spacing "even";
        String axis "Y";
        Int32 NAVO_code 1;
        String _CoordinateAxisType "Lat";
    }
    lon {
        String units "degrees_east";
        String long_name "Longitude";
        String standard_name "longitude";
        String modulo "360 degrees";
        String axis "X";
        Int32 NAVO_code 2;
        String _CoordinateAxisType "Lon";
    }
    time {
        String long_name "Forecast time for ForecastModelRunCollection";
        String standard_name "time";
        String calendar "proleptic_gregorian";
        String units "hours since 2026-10-30 12:00:00.000 UTC";
        Float64 missing_value NaN;
        String _CoordinateAxisType "Time";
    }
    time_run {
        String long_name "run times for coordinate = time";
        String standard_name "forecast_reference_time";
        String calendar "proleptic_gregorian";
        String units "hours since 2026-10-30 12:00:00.000 UTC";
        Float64 missing_value NaN;
        String _CoordinateAxisType "RunTime";
    }
    NC_GLOBAL {
        String classification_level "";
        String distribution_statement "Approved for public release; distribution unlimited.";
        String downgrade_date "not applicable";
        String classification_authority "not applicable";
        String institution "Fleet Numerical Meteorology and Oceanography Center (FNMOC)";
        String source "HYCOM archive file, GLBz0.04";
        String comment "p-grid";
        String field_type "instantaneous";
        String Conventions "CF-1.4, NAVO_netcdf_v1.1";
        String grid_name "glby0.08";
        String area_name "glby0.08";
        String contact "FNMOC CDO, 831-657-1406";
        String operational_status "pre-operational";
        String generating_model "ESPC-D V02: HYCOM 2.2.99, CICE 5.1.2, expt_03.1";
        String input_data_source "FNMOC NAVGEM, Satellite SSH, SST, SMMI, in situ observations";
        String reference "https://portal.fnmoc.navy.mil/";
        String created_on "2026-11-07 01:50:57";
        String time_origin "2026-11-06 12:00:00";
        String _CoordSysBuilder "ucar.nc2.dataset.conv.CF1Convention";
        String cdm_data_type "GRID";
        String featureType "GRID";
        String location "Proto fmrc:FMRC_ESPC-D-V02_ssh";
        String history "FMRC Best Dataset";
    }
}
