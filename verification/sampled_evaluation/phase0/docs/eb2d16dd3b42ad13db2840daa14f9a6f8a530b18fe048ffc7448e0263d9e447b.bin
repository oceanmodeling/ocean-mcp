CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
C                                                                             C
C Program Name: estofs_poitn_water_level.f                                    C
C                                                                             C
C Technical Contact(s): Name: Yuji Funakoshi       Org: NOS/OCS/CSDL/MMAP     C
C                       Phone: 301-7132809 ext.113                            C
C                       E-Mail: yuji.funakoshi@noaa.gov                       C
C                                                                             C
C Abstract:                                                                   C
C This program is used to create subtidal water level and archive all data    C
C Note: In order to compile this code, NetCDF library is required             C
C NetCDF Libibrary on NCEP CCS: /usrx/local/bin/lib                           C
C                                                                             C
C Usage: ./estofs_subtidal_water_level.ctl < swl.ctl                          C
C                                                                             C
C Language: (ex. Fortran 90)                                                  C
C                                                                             C
C Compiling/Linking Syntax: gmake -f makefile                                 C
C                                                                             C
C Target Computer: CIRRUS/STRATUS at NCEP                                     C
C                                                                             C
C Estimated Execution Time: < 10 minutes                                      C
C                                                                             C
C Suboutines/Functions Called:                                                C
C Unit No.   Name       Directory Location         Description                C
C                                                                             C
C Input Files:                                                                C
C Unit No.   Name       Directory Location         Description                C
C                                                                             C
C Output Files:                                                               C
C                                                                             C
C Input Parameters in swl.ctl:                                                C
C                                                                             C
C Libraries Used: see the makefile                                            C
C                                                                             C
C Author Name: Yuji Funakoshi                      Creation Date: Oct, 2011   C
C                                                                             C
C Revisions:                                                                  C
C Date               Author                        Description                C
C                                                                             C
C Remarks:                                                                    C
C                                                                             C
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
      implicit none
      include 'netcdf.inc'

!-------   Input file names and WL names in NetCDF   ------- 
      integer iargc, argcount
      character*2048 cmdlinearg, datafile(20)
      character*120 buffer, cwlfile, htpfile, outfile
      character*(*) time_name, station_name, zeta_name
      parameter ( time_name = 'time' )
      parameter ( station_name = 'station' )
      parameter ( zeta_name = 'zeta' )

!-------   Station name from estofs_station.ctl -------
      integer station_num
      character*120 stnfile
      character*92 longlabel
      character*6 stnid
      character*7 sid, lat, lon
      character*2 ymdh_now
      character*2 cyc
      character*12, allocatable :: ymdhm(:)

      integer i,j,k
!-------   Variable in NetCDF   ------- 
      integer ncid, retval
      integer time, station
      integer time_dimid, station_dimid
      integer zeta_varid 
      real*8, allocatable :: cwl(:,:), zeta(:,:)
      real*8, allocatable :: htp(:,:)
      real*8 residual
      real*8 mllw
      integer, allocatable :: cwl_ft(:,:)
      real*8, allocatable :: swl(:,:)

!-------   Station variable  -------
      integer iyear, imonth, iday, ihour, imins
      real*8  dayj, dummy
      real*8, allocatable :: jday(:)

      argcount = iargc() ! count up command line options
      if (argcount.gt.0) then
        i=0
         do while (i.lt.argcount)
          i = i + 1
          call getarg(i,cmdlinearg)
          write(6,*) "INFO: processing ",trim(cmdlinearg),"."
          datafile(i)=trim(cmdlinearg)
          end do
      end if

!-------   Combined Water Level at the fields   -------
!-------   Open Netcdf file   -------
      retval = nf_open( trim(datafile(1)), nf_nowrite, ncid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Get station and time dimension, and zeta variable   -------
      retval = nf_inq_dimid( ncid, time_name, time_dimid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)
      retval = nf_inq_dimid( ncid, station_name, station_dimid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)
      retval = nf_inq_varid( ncid, zeta_name, zeta_varid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Read station and time length  -------
      retval = nf_inq_dimlen ( ncid, time_dimid, time )
      if ( retval .ne. nf_noerr ) call handle_err(retval)
      retval = nf_inq_dimlen ( ncid, station_dimid, station )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Allocate three water level   ------
      allocate(ymdhm(time))
      allocate(jday(time))
      allocate(zeta(station,time))
      allocate(cwl(time,station),htp(time,station),swl(time,station))
      allocate(cwl_ft(time,station))

!-------   Read zeta data  -------
      retval = nf_get_var_double( ncid, zeta_varid, zeta )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Transform allary   ------
      write(*,*) time, station
      k=0
      do j = 1, time 
        k = k + 1
        do i = 1, station 
          cwl(k,i) = zeta(i,j)
        end do
      end do

!-------    Close the file   -------
      retval = nf_close(ncid)
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Harmonic Tidal Prediciton at the fields   -------
! -------   Open Netcdf file   -------
      retval = nf_open( trim(datafile(2)), nf_nowrite, ncid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Get station and time dimension, and zeta variable   -------
      retval = nf_inq_dimid( ncid, time_name, time_dimid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)
      retval = nf_inq_dimid( ncid, station_name, station_dimid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)
      retval = nf_inq_varid( ncid, zeta_name, zeta_varid )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Read station and time length  -------
      retval = nf_inq_dimlen ( ncid, time_dimid, time )
      if ( retval .ne. nf_noerr ) call handle_err(retval)
      retval = nf_inq_dimlen ( ncid, station_dimid, station )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Read zeta data  -------
      retval = nf_get_var_double( ncid, zeta_varid, zeta )
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!-------   Transform allary   ------
      write(*,*) time, station
      k=0
      do j = 1, time
        k = k + 1
        do i = 1, station
          htp(k,i) = zeta(i,j)
        end do
      end do

!-------    Close the file   -------
      retval = nf_close(ncid)
      if ( retval .ne. nf_noerr ) call handle_err(retval)

!--------  Read day and cycle  --------
      read(datafile(3),'(a2)') ymdh_now
      read(datafile(4),'(a2)') cyc

!--------  Read station number  --------
      open(60,file=trim(datafile(5)))
      read(60,'(i4)') station_num
      open(61,file=trim(datafile(6)))
      do i = 1, time
         read(61,'(a12)') ymdhm(i)
      end do

!--------  Read output file name  --------
      open(54,file=trim(datafile(7)))
      write(54,'(A6,X,A4,X,A2,A2,A2)')'ESTOFS','KWNO',
     &ymdh_now,cyc,'00'
      write(54,'(A39,3X,A30)')'GFS BASED STORM SURGE (IN TENTHS OF FT)',
     &'NOT VALID FOR TROPICAL STORMS'
      if ( cyc == '00' ) then
        write(54,99)'01Z','06Z','12Z','18Z','00Z'
      else if ( cyc == '06' ) then
        write(54,99)'07Z','12Z','18Z','00Z','06Z'
      else if ( cyc == '12' ) then
        write(54,99)'13Z','18Z','00Z','06Z','12Z'
      else 
        write(54,99)'19Z','00Z','06Z','12Z','18Z'
      end if
   99 format(A3,12X,A3,15X,A3,15X,A3,15X,A3)

!======================
      do j = 1, station_num
!======================

!--------   read station information   ---------
        read(60,'(a6,x,a7,x,f5.4,2x,a92)') stnid, sid, mllw, longlabel

!-------   Output file at each station   -------
        open(51,file='./'//trim(adjustL(stnid))//'.cwl')
!        open(52,file='./'//trim(adjustL(stnid))//'.htp')
!        open(53,file='./'//trim(adjustL(stnid))//'.swl')

      k = 0
!===================
      do i = 1, time
!===================

        write(51,100) ymdhm(i), cwl(i,j)
!        write(52,100) ymdhm(i), htp(i,j)
        if ( cwl(i,j) == -99999 .or. htp(i,j) == -9999 ) then
          swl(i,j) = -99999
        else
          residual = cwl(i,j) - htp(i,j)
          swl(i,j) = residual
        end if
!        write(53,100) ymdhm(i), swl(i,j)
  100   format(A12,F20.10)

!-------   Convert wl for ET-Surge web site format   -------
        if ( i >= 60 .and. i <= 1080 ) then
          if ( mod(i,10) == 0 ) then
            k = k + 1
            if ( cwl(i,j) /= -99999 ) then
              cwl_ft(k,j) = nint(cwl(i,j) * 3.280833d0 * 10.d0 ) ! convert meter to ft and in tenths of ft
            else
              cwl_ft(k,j) = -99
            end if
          end if
        end if

!===========
      end do
!===========

!-------   Output (combined waterlevel) files for MDL ET-Surge Web Site   -------
        write(54,'(A92,I4)')longlabel,cwl_ft(1,j)
        write(54,'(24(I4))') ( cwl_ft(k,j), k = 2, 97 ) 

!===========
      end do
!===========

      end program

      subroutine handle_err(errcode)
      implicit none
      include 'netcdf.inc'
      integer errcode

      print *, 'Error: ', nf_strerror(errcode)
      stop 2
      end
