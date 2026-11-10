#!python3

#!/mdlsurge/save/bin/tclsh
#-----------------------------------------------------------------------------
# post_etsurge_linux.tcl --
#     This program generates a graph which combines the extra-tropical storm
#   surge with a computed tide, and observations (where available) to create
#   an estimate of the combined water level.  It also creates a text file of the
#   same results, and can create status maps for a particular region and date.
#   The observation file archive and the surge archive are updated by seperate
#   code.
#
# 10/2000 Arthur Taylor (RSIS/MDL) Created
#  5/2002 Arthur Taylor (RSIS/MDL) Updated
# 01/2010 Anne W Kramer (Wyle IS) Updated
# 10/2023 Soroosh Mani (NOS/OCS/CSDL/CMMB) To Python
#
# Notes:
#-----------------------------------------------------------------------------
# Global variables:
#   RAY1(...)   : Variable that holds all data for calculations & output.
#     graph       : Name of main graph to pass to graph widget
#     gdFile      : File to save the graph to.
#     gdFiletype  : Filetype of gdFile.
#     im          : The main current opened gd image.
#     statusList  : The stations for which status is calculated, usually all.
#     txtFile     : Filname of output text file.
#     curAbrev    : Abbreviation for name of current station.
#     Wid         : The Width of the main gd image.
#     Hei         : The Height of the main gd image.
#     begTime     : Start time of data.
#     endTime     : Stop time of data.
#     numHours    : Total hours of data ((end+beg)*24 +1)
#     <hr>        : is hours after begTime.
#     (<hr>,cwl)  : 99.9 or cwl.
#     (<hr>,obs)  : 99.9 or observation.
#     (<hr>,anom) : 99.9 or anom (obs-(cwl)).
#     (<hr>,pred) : 99.9 or cwl+anom.
#     <stn>       : Station identifier.
#     <tm_pd>     : Time period in hours for status calculation.
#     (<stn>,status<tm_pd>)
#                 : Status (red, yellow, or green) for <stn> and <tm_pd>.
#     anomList    : List of average anomaly paired with station abbreviation.
#     numDays     : Number of days before date given to add results to graph.
#     now         : Date/time passed to the program.
#     cur         : Truncated day & hour for beginning of graph.
#     fcastDelay  : Hours of delay time for forecast.
#     fSurge      : 1 - include surge on graph (default), 0 - do not include.
#     fTide       : 1 - include tide on graph (default), 0 - do not include.
#     fObs        : 1 - include obs. on graph (default), 0 - do not include.
#     fAnom       : 1 - include anomaly on graph (default), 0 - do not include.
#     doAll       : 1 - calculate for all stations, 0 - do not (default).
#     fStat       : 1 - produce status map, 0 - do not, set by user(fMap).
#   
#   user(...)   : Variable that holds all command line input results.
#     mapRegion   : 2 letter abbreviation for status map region.
#     mapCorner   : 2 letter designation for corner of status map for legend.
#     mapIndex    : number for status map region.
#     fMap        : 1 - produce status map, 0 do not (default).
#     output      : 0,3 - graph & text (default), 1 - text only, 2 - graph only.
#     date        : date/time passed to program, default 01/01/2009 00:00:00.
#     stationList : station passed to program, default Bar Harbor, ME.
#     log         : 0 - no log messages (default), 1 - log messages to stdout.
#     
#   src_dir     : Path of the source directory.
#-----------------------------------------------------------------------------

import argparse
import logging
import os
import sys
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import numpy as np
import pandas as pd
import xarray as xr

sys.path.append(os.environ.get('LIBstofs'))  # OR set PYTHONPATH
#sys.path.append(DATA / 'lib/etss')
import archive  # replace 'archive.tcl'
#import tide3  # replace 'libtide.so'


DATA = Path(os.environ.get('DATA'))


GMT = pytz.timezone('gmt')
ZONES = {
    'CST': pytz.timezone('US/Central'),
    'EST': pytz.timezone('US/Eastern'),
    'HST': pytz.timezone('US/Hawaii'),
    'PST': pytz.timezone('US/Pacific'),
    'YST': pytz.timezone('US/Alaska'),
}
DT64REF = np.datetime64('1970-01-01T00:00:00')


logging.basicConfig(filename=f'{DATA}/log/extract.log', filemode='a')
_logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
#  Parsing Command Line Input Arguments
# ------------------------------------------------------------------------------
MAP_REGION = {
    'ne': {'stationList': 1, 'mapIndex': 1, 'mapCorner': "TL"},
    'me': {'stationList': 25, 'mapIndex': 2, 'mapCorner': "BL"},
    'se': {'stationList': 40, 'mapIndex': 3, 'mapCorner': "TL"},
    'gf': {'stationList': 49, 'mapIndex': 4, 'mapCorner': "BL"},
    'wc': {'stationList': 64, 'mapIndex': 5, 'mapCorner': "BL"},
    'ak': {'stationList': 82, 'mapIndex': 6, 'mapCorner': "BR"},
    'ga': {'stationList': 125, 'mapIndex': 7, 'mapCorner': "TR"},
}


def _to_datetime(xr_dt64):
    ts = (np.datetime64(xr_dt64, 'ns') - DT64REF) / np.timedelta64(1, 's')
    return datetime.utcfromtimestamp(ts)


def parse_cli():

    parser = argparse.ArgumentParser()

    station_group = parser.add_mutually_exclusive_group(required=True)
    station_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Do all stations and all maps'
    )
    # TODO: What is station list type input?
    station_group.add_argument(
        '--station', '-s',
        help=(
            'Choice for stations: can be station index number,'
            + ' station abbreviation, or the city, state of the station'
        )
    )

    parser.add_argument(
        '--map', '-m', 
        choices=['ne', 'me', 'se', 'gf', 'wc', 'ak', 'ga'],
        help=(
            'Crate status map for region:'
            + '\n    ne - Northern East Coast'
            + '\n    me - Middle East Coast'
            + '\n    se - Southern East Coast'
            + '\n    gf - Gulf Coast'
            + '\n    wc - West Coast'
            + '\n    ak - Alaska, West and North'
            + '\n    ga - Gulf of Alaska'
        )
    )

    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        '--date', '-d',
        type=pd.to_datetime,
        help=(
            'Choice for date in ISO 8601-like format.'
            + 'If offset is not provided it\'s assumed to be UTC'
        )
    )
    date_group.add_argument(
        '--now', '-n', action='store_true', help='Use the current time'
    )

#    parser.add_argument(
#        '--graph', '-g',
#        action='store_true',
#        help='Include station graph output'
#    )

    parser.add_argument(
        '--text', '-t',
        action='store_true',
        help='Include station text output'
    )
    parser.add_argument(
        '--datum', '-w',
        choices=['mllw', 'msl', 'hat'],
        default='msl',
        help='Choice for vdatum'
    )
    parser.add_argument(
        '--log', '-l',
        action='store_true',
        help='Output log messages to stdout',
    )

    parser.add_argument(
        '--begin', '-b',
        type=pd.to_datetime,
        help=(
            'Date range start in ISO 8601-like format.'
            + 'If offset is not provided it\'s assumed to be UTC'
        )
    )

    parser.add_argument(
        '--end', '-e',
        type=pd.to_datetime,
        help=(
            'Date range end in ISO 8601-like format.'
            + 'If offset is not provided it\'s assumed to be UTC'
        )
    )

    args = parser.parse_args()


    return args


def process_cli(args):
    user = {}
#    user['mapRegion'] = 0
    user['mapCorner'] = None
    user['mapIndex'] = 0
#    user['fMap'] = False
    user['output'] = 0
    user['date'] = datetime.now(pytz.timezone('gmt'))
    user['now'] = False
    user['allStations'] = False
    # TODO: What is station list type?!
    user['stationList'] = ""
    user['log'] = False
    user['dateRange'] = False
    user['dateStart'] = user['date']
    user['dateEnd'] = user['dateStart'] + timedelta(hours=6)
    user['f_datum'] = args.datum

    if args.map is not None:
#        user['fMap'] = True
#        user['mapRegion'] = args.map
        for k, v in MAP_REGION[args.map].items():
            user[k] = v

    if args.text:
        user['output'] |= 1
        print("Textual output included")
#    if args.graph:
#        user['output'] |= 2
#        print("Graphical output included")


    if args.now:
        # We have date in GMT
        user['date'] = datetime.now(pytz.timezone('gmt'))
        user['now'] = True
    else:
        user['date'] = args.date
        user['now'] = False

    print(f"Date chosen as {user['date'].strftime('%D %T')}")

    if args.all:
        user['allStations'] = True
    else:
        user['allStations'] = False
        user['stationList'] = args.station
        print(f"Station chosen is {','.join(args.station)}")

    if args.log:
        user['log'] = True
        print("Printing log statements to screen")


    if args.begin is not None:
        user['dateStart'] = args.begin
        user['dateRange'] = True

    if args.end is not None:
        user['dateEnd'] = args.end
        user['dateRange'] = True


    # Use tz-naive datetimes in GMT time
    for nm in ['date', 'dateStart', 'dateEnd']:
        if user[nm].tzinfo is None:
            # If it's tz-naive assume it's in GMT
            continue

        # Else convert to GMT and make it naive
        user[nm] = user[nm].astimezone(GMT).replace(tzinfo=None)


    return user


#*******************************************************************************
# Procedure Init_Time
#
# Purpose:
#     Initiates beginning and end times for use in Refresh.
#
# Variables:(I=input)(O=output)
#   ray_name   (I) Global array to store the data in.
#   days_before (I) Number of days before ray(now) to get results.
#   days_after (I) Number of days after ray(now) to get predictions.
#
# Returns: NULL
#
# History:
#    10/2000 Arthur Taylor created
#
# Notes:
#   Adjusts ray time values and initiates values at 99.9 
#*******************************************************************************
def Init_Time(ds, days_before, days_after):
    nHrs = (days_after + days_before) * 24 + 1
    hrs = np.arange(nHrs)
    ret_ds = xr.Dataset(
        data_vars=dict(
            **ds.data_vars.variables,
            begTime=ds['cur'] - np.timedelta64(days_before, 'D'),
            endTime=ds['cur'] + np.timedelta64(days_after, 'D'),
            numHours=nHrs,
            cwl=('hr', np.ones(hrs.shape) * 99.9),
            obs=('hr', np.ones(hrs.shape) * 99.9),
            anom=('hr', np.ones(hrs.shape) * 99.9),
            pred=('hr', np.ones(hrs.shape) * 99.9),
        ),
        coords={
            **ds.coords.variables,
            'hr': hrs,
        },
        attrs=ds.attrs,
    )

    return ret_ds


#*******************************************************************************
# Procedure Get_Tide
#
# Purpose:
#     Read a file which contains the tide data for a particular station.
#
#  Unfortunately a secondary station doesn't have ability to automatically
#  subtract the mllw/msl.  So in that case an adj is passed which can be
#  subtracted.
#
# Variables:(I=input)(O=output)
#   ray_name   (I) Global array to store the data in.
#   tide_stn   (I) The station in question.
#   zone       (I) The time zone for the results
#
# Returns: 
#    True on success, False on failure
#
# History:
#    10/2000 Arthur Taylor created
#
# Notes:
#   Sets ray(<hr>,tide)
#*******************************************************************************
def Get_Tide(mut_ds, tide_stn, tzinfo, f_datum, adjust1, adjust2):

    raise NotImplementedError("This code is from the old implementation!")

    old_dir = None
    cwd = Path().absolute()

    if not (cwd / 'ft03.dta').exists():
        if (DATA / 'data' / 'ft03.dta').exists():
            old_dir = DATA
            os.chdir(DATA / 'data')
        else:
            print("Cannot find ft03.dta file!")
            return False

    # if the tide number in cron.bnt is negative, this will flag
    # TideC_stn to perform calculations for a secondary station
    f_secondary  = False
    if tide_stn < 0:
        f_secondary = True
        tide_stn = -tide_stn

    # TideC_stn takes data in Local Standard Time (for station) 
    # Flagging for season (is_seasonal) and if using MLLW (add_mllw)
    #
    # mut_ds times are tz-naive and assume to be in GMT
    loc_datetime = GMT.localize(
        _to_datetime(mut_ds['begTime'].item())
    ).astimezone(tzinfo)

    try:
        # Tide index needs to be adjusted later based on DST.
        # So an additional hour prior to `begTime` is read
        # at the beginning of tides (`begTime - 1` to `endTime`).
        tides = tide3.TideC_stn(
            "hourly",
            station=tide_stn,
            date=loc_datetime - timedelta(hours=1),
            numHour=int(mut_ds['numHours']) + 1,
            initHeight=0,
            add_mllw=True,
            is_seasonal=True,
            is_secondary=f_secondary
        )
    except ValueError as ex:
        _logger.error(f'Error reading tides for station {tide_stn}...')
        _logger.error(ex)
        return False

    if old_dir is not None:
        os.chdir(old_dir)

    # mut_ds['cur'] holds the valid time, so it tells us if
    # we are putting the tide in EDT or EST. If EDT, must shift which
    # values are stored.
    daylight_adj = 1
    is_dst = bool(
        GMT.localize(
            _to_datetime(mut_ds['cur'].item())
        ).astimezone(tzinfo).dst()
    )
    if is_dst:
        daylight_adj = 0

    # Compared to the original code the adjustment role is reversed.
    # The original code used adjustment to index the STORAGE array,
    # while here it indexes the TIDE result array from TideC_stn.
    # if not DST: store `begTime` to `endTime`
    # else: store `begTime - 1` to `endTime - 1`
    #
    # NOTE: stored tides length is always the same now
    tides = tides[daylight_adj:][:int(mut_ds['numHours'])]
    if f_datum == "mllw":
        mut_ds['tide'].loc[:] = tides
    elif f_datum == "msl":
        mut_ds['tide'].loc[:] = tides + adjust1
    else:
        mut_ds['tide'].loc[:] = tides + adjust2

    return True


#*******************************************************************************
# Procedure Get_Anom
#
# Purpose:
#     Calculates the anomaly and ensures the anomaly is reasonable.
#
# Variables:(I=input)(O=output)
#   ray_name   (I) Global array to store the data in.
#   filt_anom  (I) A reasonable anomaly value, dictated by cron.bnt
#                  3ft for Gulf Coast, 5ft elsewhere
#
# Returns: NULL
#
# History:
#    10/2000 Arthur Taylor created
#
# Notes:
#   Adjusts ray(anomList)
#*******************************************************************************
def Get_Anom(mut_ds, filt_anom):

    # Filter out all obs after (now) for historical plot.
    times = (
        mut_ds['begTime'].values
        + np.timedelta64(1, 'h') * mut_ds['hr'].values
    )
    mut_ds['obs'].loc[times > mut_ds['now'].values] = 99.9

    # Do a filter for "Constant" obs.
    # This filter even with a 6 hour const check fails for Waveland MS.
    # So I am going to try a 9 hour const check.
    Const_Hour_Check = 9

    cnt = 0
    last = 99.9
    i_start = 0
    marks = []
    obs = mut_ds['obs'].values
    for i in range(mut_ds['numHours'].item()):
        hr = i
        cur = obs[i]

        if cur == 99.9:
            continue

        num_match = 1
        
        vec = obs[i+1:]
        idx_next_notconst = np.where(~np.isclose(vec, cur, atol=0.08))[0]
        if len(idx_next_notconst) == 0:
            num_match += len(vec)
        else:
            # If the next non-const is at index 4, then the 
            # 4 before it are const!
            num_match += idx_next_notconst[0]
            
        
        if num_match >= Const_Hour_Check:
            # mark every hour's worth of the constant observation patch
            marks.append((hr, num_match))

    # Setting the constant sections of observations to the bad flag of 99.9
    for hr, num_match in marks:
        # NOTE: loc() upper bound is inclusive
        mut_ds['obs'].loc[hr:hr + num_match - 1] = 99.9

    
    # Now to calculate the anomaly.  The anomaly needs at least 12 values over
    # the 5 day period before the average anomaly can be trusted.  The anomaly
    # also needs to be in a "reasonable" range (3ft for Gulf Coast, 5ft
    # otherwise).  Anomaly is in reference to 0, rather than in reference to the
    # average anomaly.
    #
    # setting up the values for calculating the average anomaly
    tot_anom =  0
    anom_cnt = 0
    mut_ds['last_obsTime'] =  pd.NaT
    last_obsHr = 0
    last_anomValue = 0
#    f_fixObs = 0


    df = mut_ds[['cwl', 'obs', 'anom']].to_dataframe()
    valid = (df[['cwl', 'obs']] != 99.9).all(axis=1)
    df.loc[valid, 'anom'] = (df.obs - df.cwl)[valid]
    reasonable = df.anom.abs() < filt_anom
    anom_cnt = reasonable.sum()
    if anom_cnt:
        tot_anom = df.anom[reasonable].sum()
        mut_ds['anom'].loc[df[reasonable].index] = df.anom[reasonable]
        mut_ds['obs'].loc[df[valid & ~reasonable].index] = 99.9
        last_anomValue = df.anom[reasonable].iloc[-1]
    chk = df.obs < 99
    if chk.sum():
        last_obsHr = df.obs[chk].index[-1]
        mut_ds['last_obsTime'] = (
            mut_ds['begTime'] + np.timedelta64(last_obsHr, 'h')
        )


    # If there are at least 12 good values of the anomaly, set the hourly anomaly
    # and the anomaly value in anomList to the average of the total anomaly from
    # above.  Otherwise, set the hourly anomaly to 0 for later calculations, and
    # then flag as a bad value in anomList with the value of 99.
    hrsAfter = mut_ds.hr > last_obsHr
    within12Hr = hrsAfter & (mut_ds.hr < last_obsHr + 12)
    nullAnom = mut_ds['anom'] == 99.9
    avg = 99
    if anom_cnt >= 12:
        avg = tot_anom / anom_cnt

        mut_ds['anom'].loc[hrsAfter  & nullAnom] = avg
        mut_ds['anom'].loc[within12Hr & nullAnom] = (
            last_anomValue
            + (avg - last_anomValue)
            * (mut_ds.hr[within12Hr & nullAnom] - last_obsHr) / 12
        )
    else:
        avg = 99
        mut_ds['anom'].loc[hrsAfter & nullAnom] = 0

    mut_ds.attrs['anomList'].append((mut_ds['curAbrev'], avg))



#*******************************************************************************
# Procedure Get_Pred
#
# Purpose:
#     Sets predicted combined water for Calc_Status.
#
# Variables:(I=input)(O=output)
#   ray_name   (I) Global array to store the data in.
#
# Returns: 99.9 if cwl or anom not correct.
#
# History:
#    10/2000 Arthur Taylor created
#
# Notes:
#   Sets ray(<hr>,pred)
#*******************************************************************************
def Get_Pred(mut_ds):
    # loop runs for all values of time in case ray(last_obsTime) is still set -1
    times = mut_ds['begTime'].values + np.arange(
        np.timedelta64(0, 'h'),
        np.timedelta64(mut_ds['numHours'].item(), 'h')
    )
    pred_time = np.logical_or(
        times > mut_ds['last_obsTime'].values,
        pd.isna(mut_ds['last_obsTime'])
    )
    df = mut_ds[['cwl', 'anom', 'pred']].to_dataframe()
    valid = pred_time & (df[['cwl', 'anom']] != 99.9).all(axis=1)
    df.loc[valid, 'pred'] = (df.cwl + df.anom)[valid]
    mut_ds['pred'].loc[df[valid].index] = df.pred[valid]


#*******************************************************************************
# Procedure Output_Text
#
# Purpose:
#     Creates text file of results.
#
# Variables:(I=input)(O=output)
#   ray_name     (I) Global array to store the data in.
#   display_days (I) The number of days to display data.
#   title        (I) Full name of the station to be put in the text file title.
#   HAT          (I) Highest Astronomical Tide. 
#
# Returns: Text file of results.
#
# History:
#    10/2000 Arthur Taylor created
#
# Notes:
#   Does not adjust ray
#*******************************************************************************
def Output_Text(mut_ds, display_days, title, mat, f_datum):


    with (
#        open(mut_ds['txt_file'].item(), 'w') as fp,
        open(mut_ds['anom_file'].item(), 'w') as fpan
    ):
        
        # mut_ds times are tz-naive and assumed to be in GMT
        now = _to_datetime(mut_ds['now'].item())

#        fp.write(
#            f"#{title} : {now.strftime('%m/%d/%Y %T')} GMT"
#            + f' (units in feet {f_datum.upper()})\n'
#        )
#        fp.write(
#            "#Date(GMT), Surge,   Tide,    Obs,   Fcst,   Anom, Comment\n"
#        )
#        fp.write(
#            "#------------------------------------------------------------\n"
#        )
#        
#        # time value to begin outputting text results
        start = (
            _to_datetime(mut_ds['cur'].item())
            - timedelta(days=display_days)
        )
#
#        # f_max: flag used to track when to label a max or a min for
#        # combined water level
#        # 0 - no good value for combined water level
#        # 1 - max
#        # -1 - min
#        # 2 - only 1 value for combined water level
#        f_max = 0
#        # number to compare to next combined water level to determine f_max 
#        big = 99.9
#        # flag to output a new full label after the last observation time
#        f_label = 0
#        
#        # looping through all times to find trend of combined water level
#        obs = mut_ds.obs.values.copy()
#        pred = mut_ds.pred.values.copy()
        anom = mut_ds.anom.values.copy()
#        tide = mut_ds.tide.values.copy()
#        surge = mut_ds.surge.values.copy()
#        last_obsTime = mut_ds['last_obsTime'].values
#        assert len(obs) == len(pred) == mut_ds.numHours.item()
        for i in range(mut_ds['numHours'].item()):
            # mut_ds has tz-naive time assumed to be in GMT
            time = (
                _to_datetime(mut_ds['begTime'].item())
                + timedelta(hours=i)
            )
            hr = i
#
#            # No slope info
#            if f_max == 0:
#                if obs[i] != 99.9:
#                    big = obs[i]
#                    f_max = 2
#                elif pred[i] != 99.9:
#                    big = pred[i]
#                    f_max = 2
#
#            # First data after no-slope
#            elif f_max == 2:
#                if obs[i] != 99.9:
#                    if big < obs[i]:
#                        f_max = 1
#                    else:
#                        f_max = -1
#                    big = obs[i]
#                elif pred[i] != 99.9:
#                    if big < pred[i]:
#                        f_max = 1
#                    else:
#                        f_max = -1
#                    big = pred[i]
#
            if time < start:
#                # if it is before start of text output, still establish
#                # which trend the combined water level is following
#                if f_max == 1:
#                    if obs[i] != 99.9:
#                        if big > obs[i]:
#                            f_max = -1
#                        big = obs[i]
#                    elif pred[i] != 99.9:
#                        if big > pred[i]:
#                           f_max = -1 
#                        big = pred[i]
#                elif f_max == -1:
#                    if obs[i] != 99.9:
#                        if big < obs[i]:
#                            f_max = 1
#                        big = obs[i]
#                    elif pred[i] != 99.9:
#                        if big < pred[i]:
#                            f_max = 1
#                        big = pred[i]
                pass
            else:
#                # now after start of text output, check values for
#                # max and min combined water level, and print values
#                if time != start:
#                    if f_max == 1:
#                        if obs[i] != 99.9:
#                            if big > obs[i]:
#                                fp.write("  (max)")
#                                f_max = -1
#                            big = obs[i]
#                        elif pred[i] != 99.9:
#                            if big > pred[i]:
#                                fp.write("  (max)")
#                                f_max = -1
#                            big = pred[i]
#                    elif f_max == -1:
#                        if obs[i] != 99.9:
#                            if big < obs[i]:
#                                fp.write("  (min)")
#                                f_max = 1
#                            big = obs[i]
#                        elif pred[i] != 99.9:
#                            if big < pred[i]:
#                                fp.write("  (min)")
#                                f_max = 1
#                            big = pred[i]
#                    fp.write("\n")
#
#                # inserts a new label after the last observation time is printed
#                if f_label == 1:
#                    fp.write(
#                        "#------------------------------------------------------------\n"
#                    )
#                    fp.write(
#                        "#Date(GMT), Surge,   Tide,    Obs,   Fcst,   Anom, Comment\n"
#                    )
#                    fp.write(
#                        "#------------------------------------------------------------\n"
#                    )
#                    f_label = 0
#
#                # printing values on one line, including combined water level
#                fp.write(f'{time.strftime("%m/%d %H")}Z,')
#                fp.write(f'{surge[i]:7.2f},')
#                fp.write(f'{tide[i]:7.2f},')
#                fp.write(f'{obs[i]:7.2f},')
#                fp.write(f'{pred[i]:7.2f},')
#                fp.write(f'{anom[i]:7.2f},')
#                if obs[i] != 99.9 and obs[i] > mat:
#                    fp.write(
#                        f' {obs[i] - mat:5.2f} ft above HAT'
#                    )
#                if pred[i] != 99.9 and pred[i] > mat:
#                    fp.write(
#                        f' {pred[i] - mat:5.2f} ft above HAT'
#                    )
#                if last_obsTime == time:
#                    f_label = 1
                #-------- anomaly only
                if anom[i] == 99.9:
                    mut_ds['anom'].loc[hr] = 0.00
                    anom[i] = 0.00
                fpan.write(
                    f"{hr} {anom[i] * 0.3048:7.2f}"
                    + f" {time.strftime('%Y%m%d%H')}\n"
                )
#        fp.write("\n")


#*******************************************************************************
# Procedure Refresh
#
# Purpose:
#     Creates the graph and/or text file for a given station and date.
#
# Variables:(I=input)(O=output)
#   ray_name   (I) Global array to store the data in.
#   obs_stn    (I) station to be passed to Read_ObsFile
#   tide_stn   (I) station to be passed to Get_Tide
#   cwl_file   (I) filename for Read_WaterLevel
#   title      (I) full name of the station
#   arch_cwl   (I) name of archived waterlevel data file
#   temp_file  (I) name of temporary file to be passed to Read_ObsFile
#   days_before (I) number of days to read before specified date/time
#   arch_obs   (I) archived observation file for station
#   display_days (I) number of days to display
#   mllw       (I) mean lower low water for station from cron.bnt, passed to
#                  Create_Plot, Output_Text and Get_Tide 
#   msl        (I) mean sea level for station, used by Get_Tide & Create_Plot
#   mhhw       (I) mean higher high water for station, used by Create_Plot 
#   zone       (I) timezone for station and date
#   mat        (I) max. astronomical tide for station
#   filt_anom  (I) reasonable value for anomaly for station
#
# Returns: NULL
#
# History:
#    10/2000 Arthur Taylor created
#    01/2010 Anne W Kramer modified
#
# Notes:
#   Adjusts ray
#*******************************************************************************
def Refresh(
    user_input,
    mut_ds,
    obs_stn: int,
    tide_stn: int,
    cwl_file,
    title,
    arch_cwl,
    temp_file,
    days_before,
    arch_obs,
    display_days,
    mllw,
    msl,
    mhhw,
    zone,
    mat,
    filt_anom,
):

    # Calculate "cur" based on now 
    # mut_ds time is tz-naive and assumed to be in GMT
    cur = (
        _to_datetime(mut_ds['now'].item())
        - timedelta(hours=mut_ds['fcastDelay'].item())
    )
    cur_date = cur.strftime('%D')
    cur_hour = cur.hour
    # truncating to correct model run time for output
    if cur_hour >= 0 and cur_hour < 6:
        cur_hour = 0
    elif cur_hour >= 6 and cur_hour < 12:
        cur_hour = 6
    elif cur_hour >= 12 and cur_hour < 18:
        cur_hour = 12
    else:
        cur_hour = 18

    # `adj_cur` is still in GMT, like `cur`
    adj_cur = datetime.strptime(
        f'{cur_date} {cur_hour}:00',
        '%m/%d/%y %H:%M'
    )
    mut_ds['cur'] = adj_cur

    # Init begTime/endTime, including number of days after current time to use,
    # and init ray elements to 99.9
    days_after = 4
    mut_ds = Init_Time(mut_ds, days_before, days_after)

    # getting waterlevel values from archived data, this function exists in archive.tcl
    archive.Read_ArchCWL(mut_ds, arch_cwl)

    # NOTE: New implementation works with combined water levels
#    if not Get_Tide(
#            mut_ds, tide_stn, zone,
#            user_input['f_datum'], mllw - msl, mllw - mat):
#        # Data for this station is corrupt, ignore the station update
#        _logger.error(
#            f'Corrupted data ... ignoring {tide_stn} {obs_stn}...'
#        )
#        return


    # will only print if user(log) present
    _logger.info("Have Read combined water levels... Get obs?")
  

    # getting observations from archived station data, function in archive.tcl
    with open(temp_file, 'w') as ap:
        if user_input['f_datum'] == "mllw":
            archive.Read_ArchObs(mut_ds, arch_obs, ap, 0)
        elif user_input['f_datum'] == "msl":
            archive.Read_ArchObs(mut_ds, arch_obs, ap, mllw - msl)
        else:
            archive.Read_ArchObs(mut_ds, arch_obs, ap, mllw - mat)
    
    # will only print if user(log) set
    _logger.info("Finished Reading obs")
    
    Get_Anom(mut_ds, filt_anom)
    Get_Pred(mut_ds)

#    if user_input['output']  in [0, 3]:
    Output_Text(
        mut_ds, display_days, title, mat - mllw, user_input['f_datum']
    )





#*******************************************************************************
# Procedure Main_Init
#
# Purpose:
#     Initializes certain graph values stored in ray.
#
# Variables:(I=input)(O=output)
#   ray_name     (I) Global array to store the data in.
#
# Returns: NULL
#
# History:
#    10/2000 Arthur Taylor created
#    01/2010 Anne W Kramer modified
#
# Notes:
#   Adjusts ray graph values
#*******************************************************************************
def Main_Init(mut_ds, datum):
    # default values
    mut_ds['numDays'] = 1.5
    mut_ds['fcastDelay'] = 3
    mut_ds['fSurge'] = 1
    mut_ds['fTide'] = 1
    mut_ds['fObs'] = 1
    mut_ds['fAnom'] = 1

    mut_ds['txt_file'] = DATA / 'default_txt.txt'
    mut_ds['anom_file'] = DATA / 'default_anom.txt'
    mut_ds.attrs['anomList'] = []

#*******************************************************************************
# Procedure Main
#
# Purpose:
#     Main function of program, loops through multiple stations if status map
#         is required.
#
# Variables:(I=input)(O=output)
#   ray_name     (I) Global array to store the data in.
#
# Returns: All specified files.
#
# History:
#    10/2000 Arthur Taylor created
#    01/2010 Anne W Kramer modified
#
# Notes:
#   Adjusts many parts of ray
#*******************************************************************************
def Main(user_input, mut_ds):
  
    datum = user_input['f_datum'].upper()
    Main_Init(mut_ds, datum)
    
    # xarray dates are tz-naive and assumed to be in GMT
    now = _to_datetime(mut_ds['now'].item())
    timeStamp = now.strftime('%y%m%d')

    with open(DATA / 'data' / 'cron.bnt', 'r') as fp:
        line = fp.readline()
        station_cnt = 0
        for line in fp:
            line = line.split(':')
            if line[0].strip() and line[0].strip()[0] == '#':
                continue

            station_cnt += 1
            if not (mut_ds['doAll']
                    or user_input['stationList'].strip().lower() == line[1]
                    or user_input['stationList'].strip().upper() == line[2]
                    or user_input['stationList'].strip().upper() == line[7].upper()
                    or user_input['stationList'] == str(station_cnt)
                    or str(user_input['mapIndex']) in line[15].split(',')
                    ):
                continue

            datum = user_input['f_datum']
            
            out_dir = DATA / datum / 'plots'
            out_dir.mkdir(exist_ok=True, parents=True)

            # removing timestamp for running "now"
            if user_input['now']:
                mut_ds['txt_file'] = out_dir / f'{line[1]}.txt'
                mut_ds['anom_file'] = out_dir / f'{line[1]}.anom'
            else:
                mut_ds['txt_file'] = out_dir / f'{line[1]}_{timeStamp}.txt'
                mut_ds['anom_file'] = out_dir / f'{line[1]}_{timeStamp}.anom'
            mut_ds['curAbrev'] = line[1]

            zone = line[16]
            # mut_ds['now'] is in tz-naive, the value is in GMT, first
            # we `localize` it and then get the value in the specified
            # timezone to check if the value in the specified timezone
            # has daylight saving offset
            tzinfo = ZONES[zone]
#            is_dst = bool(
#                GMT.localize(
#                    _to_datetime(mut_ds['now'].item())
#                ).astimezone(tzinfo).dst()
#            )
#            if zone != 'HST' and is_dst:
#                zone = f"{zone[0]}DT"

            mllw = float(line[12])
            msl = float(line[13])
            mhhw = float(line[14])
            mat = float(line[17].split('#')[0])
            filt_anom = float(line[18])
            DaysToRead = 5
            if mut_ds['numDays'] > DaysToRead:
                DaysToRead  = mut_ds['numDays']

            Refresh(
                user_input,
                mut_ds,
                line[3],
                int(line[4]),
                line[5],
                line[7],
                DATA / 'database' / f'{line[1]}.cwl',
                DATA / 'temp.txt',
                DaysToRead,
                DATA / 'database' / f'{line[1]}.obs',
                mut_ds['numDays'].item(),
                mllw,
                msl,
                mhhw,
                tzinfo,
                mat,
                filt_anom
            )

            # NOTE: Not Calc_Status (?)


#-----------------------------------------------------------------------------
# Done with Procs, start program.
#-----------------------------------------------------------------------------
if __name__ == '__main__':
    os.chdir(DATA)

    args = parse_cli()
    user = process_cli(args)

    dataset = xr.Dataset()
    dataset['doAll'] = False

    # looping for multiple dates
    j = 0
    if user['dateRange']:
        if user['dateStart'] >= user['dateEnd']:
            print(
                "        date begin and date end incompatible"
                + " or incorrectly defined, please re-enter."
            )

        # NOTE: In `process_cli` made all dates tz-naive and in GMT
        now = user['dateStart']
        while now < user['dateEnd']:
            hr_increment = 12
            now = user['dateStart'] + timedelta(hours=hr_increment * j)
            dataset['now'] = now
            user['date'] = now

            Main(user, dataset)

            j += 1

    elif user['allStations']:
        dataset['now'] = user['date']
        dataset['doAll'] = True
        Main(user, dataset)

    else:
        dataset['now'] = user['date']
        Main(user, dataset)
