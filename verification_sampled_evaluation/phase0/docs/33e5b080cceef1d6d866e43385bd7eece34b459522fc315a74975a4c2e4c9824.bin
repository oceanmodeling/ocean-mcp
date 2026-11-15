#!/usr/bin/env python3
#from pylib import *
#import sys; sys.path.append('/sciclone/data10/hjyoo/pylibs/For_NOAA/pylibs')
import sys; sys.path.append('./pylibs')

import os
import numpy as np

from pylib import read_schism_bpfile, npz_data, datestr2num, array, save_npz
from datetime import datetime
import re

import pandas as pd

#-----------------------------------------------------
if __name__ == '__main__':
    bp = read_schism_bpfile('./station.bp')

C=npz_data(); C.lon,C.lat,C.station=bp.x,bp.y,bp.station

#read data
#fnames=os.listdir('./msl/');
fnames=os.listdir('./navd_PR/');
#read each file in years
mtime=[]; station=[]; elev=[]; iflag=0
for fname in fnames:
    if not fname.endswith('.csv'): continue
    R=re.match('(\S+)_(\S+)_(\d+)_(\S+).csv',fname); sta=R.groups()[2]

    #read data
    iflag=iflag+1; print('reading {}, {}'.format(fname,iflag))
    #fid=open('./msl/{}'.format(fname),'r'); lines=fid.readlines(); fid.close(); lines=lines[1:]
    fid=open('./navd_PR/{}'.format(fname),'r'); lines=fid.readlines(); fid.close(); lines=lines[1:]
    if len(lines)<10: continue
     #parse each line
    for i in np.arange(len(lines)):
        line=lines[i].split(',')
        if line[1]=='': continue
        ctime=line[0]; index=ctime.rfind('/')
        dtime=ctime[:index] 
        doyi=datestr2num(dtime); 
        elevi=float(line[1])

        #save record
        mtime.append(doyi)
        station.append(sta)
        elev.append(elevi)        

#-save data-------
S=npz_data(); S.time=array(mtime); S.elev=array(elev)
S.station=array(station)

# add lat&lon information
Lat=dict(zip(C.station,C.lat)); Lon=dict(zip(C.station,C.lon))
S.lat=array([Lat[i] for i in S.station])
S.lon=array([Lon[i] for i in S.station])
save_npz('noaa_navd',S)
#save_npz('noaa_msl_2024',S)


