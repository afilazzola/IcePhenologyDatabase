import sys
sys.path.insert(0,'../src/')

# Import read_all_files, etc from kpmbread
# from kpmbread import *
# from kpmb_lib import doy_to_date, date_conversion
# from kpmb_plots import similar

from additional_functions import similar, doy_to_date, date_conversion, read_all_files

from IPython.display import clear_output

import re

import os
import pandas as pd
import numpy as np

import time
import configparser

from pandas.api.types import CategoricalDtype

# from pandas.errors import OutOfBoundsDatetime

origtime = time.time()

# filenames = {}

def get_all_filenames(rootdir, exclude_files=[], exclude_dirs=[]):
# Cycle through directory structure, adding files to filenames dictionary.
    filenames = {}
    for root, subdirs, files in os.walk(rootdir):
        for f in files:
            if (not np.array([e in f for e in exclude_files]).any()) & (not np.array([e in root for e in exclude_dirs]).any()):
                extension = f.split('.')[-1]
                filename = root+'/'+f
        # add filename to dictionary
                if extension in filenames:
                    filenames[extension] = filenames[extension]+[filename]
                else:
                    filenames[extension] = [filename]
    return filenames


def fix_special_cases(df):
    ##########
    # 1. Swedish Lakes
    ##########

    # Get ice on and ice off from (No column name)
    if 'tsc_value_f' in df.columns:
        indfreeze = df.tsc_value_f == 1
        indthaw = df.tsc_value_f == 2
        inddrop = df.ts_shortname_s=='NonIce.Cmd'

        df.loc[indthaw,'ice_off'] = df.loc[indthaw,'(No column name)']
        df.loc[indfreeze,'ice_on'] = df.loc[indfreeze,'(No column name)']

        df.loc[indthaw,'Fall Year'] = df.loc[indthaw,'ice_off'].apply(lambda x: int(x.split('-')[0])
                                    if (int(x.split('-')[1]) > 8) 
                                    else int(x.split('-')[0])-1)
        df.loc[indfreeze,'Fall Year'] = df.loc[indfreeze,'ice_on'].apply(lambda x: 
                                                                     int(x.split('-')[0])
                                                                        if (int(x.split('-')[1]) > 8)
                                                                        else 
                                                                     int(x.split('-')[0])-1
                                                                    )
        df = df[~inddrop].copy()


    ##########
    # 2. Extract Fall Year/Year Freeze Up from ice on and ice off columns
    ##########
    if 'date ice out' in df.columns:
        indthaw = ~df['date ice out'].isnull()
        df.loc[indthaw,'Fall Year'] = df.loc[indthaw,'date ice out'].apply(lambda x:
                                                                       x.year
                                                                           if x.month > 8 
                                                                           else
                                                                       x.year-1
                                                                    )
    if 'date ice in' in df.columns:
        indfreeze = ~df['date ice in'].isnull()
        df.loc[indfreeze,'Fall Year'] = df.loc[indfreeze,'date ice in'].apply(lambda x: 
                                                                    x.year
                                                                        if x.month > 8
                                                                        else 
                                                                    x.year-1
                                                                    )
    # Itasca Lakes (Lesley Knoll) have incorrect Year freeze up for Long Lake
    if 'Lake' in df.columns:
        indwrong = df.Lake=='Long Lake' # these have wrong Year freeze up (i.e., Fall Year)
        df.loc[indwrong, 'Year freeze up'] = np.nan

    if 'Year freeze up' in df.columns:
        indfreeze = df['Year freeze up'].isnull() & ~df['Ice Up (date)'].isnull() & ~df['Ice Up (date)'].astype(str).str.contains('unknown')
        df.loc[indfreeze,'Year freeze up'] = df.loc[indfreeze, 'Ice Up (date)'].apply(lambda x:
                                                                            x.year
                                                                                if x.month > 8
                                                                                else
                                                                            x.year-1
                                                                            )
        indfreeze = df['Year freeze up'].isnull() & ~df['Ice Out (Date)'].isnull() & ~df['Ice Out (Date)'].astype(str).str.contains('unknown')
        df.loc[indfreeze,'Year freeze up'] = df.loc[indfreeze, 'Ice Out (Date)'].apply(lambda x:
                                                                            x.year
                                                                                if x.month > 8
                                                                                else
                                                                            x.year-1
                                                                            )

    ##################
    # 3. Get Year from dates for Nipissing
    ##################

    if 'Ice off dates' in df.columns:
        indyao = df.Contributor.astype(str).str.contains('Yao') & (df.lake=='Lake Nipissing')
        df.loc[indyao,'Spring Year'] = df.loc[indyao,'Ice off dates'].apply(lambda x: x.split()[0])
        df.loc[indyao,'Spring Year'] = df.loc[indyao,'Spring Year'].apply(lambda x: x if x not in ['x','y'] else np.nan)

    ###################
    # 4. LIAG - calculate date from separate month, day , year columns
    #    and remove rivers
    #    XXand fix Erken longitude FIXES ARE APPLIED LATER (search for ARAI1, TB01)
    #    XXand fix Suwa latitude
    #    XXand fix GTB latitude
    #    XXand fix Nehmitzsee coordinates
    ###################
    if 'iceon_year' in df.columns:
        ind = df.Contributor=='LIAG' #& df['Ice on'].isnull()
        df.loc[ind,'Ice on'] = df[ind].apply(lambda row: '{:04d}-{:02d}-{:02d}'.format(int(row.iceon_year),int(row.iceon_month),int(row.iceon_day))
              if (row.iceon_day!=-999) & (~np.isnan(row.iceon_day)) else -999, axis=1)
    if 'iceoff_year' in df.columns:
        ind = df.Contributor=='LIAG' #& df['Ice off'].isnull()
        df.loc[ind,'Ice off']= df[ind].apply(lambda row: '{:04d}-{:02d}-{:02d}'.format(int(row.iceoff_year),int(row.iceoff_month),int(row.iceoff_day))
              if (row.iceoff_day!=-999) & (~np.isnan(row.iceoff_day)) else -999, axis=1)
    if 'lakeorriver' in df.columns:
        ind = (df.Contributor == 'LIAG') & (df.lakeorriver=='R')
        df = df[~ind].copy()
    
    # Erken longitude should be positive
    #ind = df.lakename.str.lower().str.contains('erken') & df.lakecode.str.contains('TB01')
    #df.loc[ind,'longitude'] = df.loc[ind,'longitude'].apply(lambda x: np.abs(x))

    # NEHMITZSEE and Stechlinsee have same coordinates. Adjust Nehmitzsee
    #ind = df.lakename.str.lower().str.contains('nehmitz') & df.lakecode.str.contains('RA2')
    #df.loc[ind, 'latitude'] =53.13
    #df.loc[ind, 'longitude']=12.99
    #manually went through these lakes and assigned new coordinates in water
    
    # these are all LIAG corrections. (get overwritten if more modern observations exist)
    liag_corrections = {
                        'ARAI1':{'Latitude':36.04}, 
                        'RAA3' :{'Latitude':44.77}, # Grand Traverse Bay                       
                        'ARAK1':{'Latitude':36.04},
                        'WSTA1':{'Latitude':36.04},
                        'YATSU1':{'Latitude':36.04},
                        'ETJ1':{'Latitude':46.171,'Longitude':-89.344}, # anderson
                        'JJM11':{'Latitude':45.754,'Longitude':-91.651}, #long
                        'JJM19':{'Latitude':46.057,'Longitude':-89.566}, # mystery
                        'JJM23':{'Latitude':46.053,'Longitude':-89.567}, # spruce
                        'JJM25':{'Latitude':44.33,'Longitude':-88.634}, # black otter
                        'MINN37':{'Latitude':44.555, 'Longitude':-92.433}, # pepin
                        'NG2':{'Latitude':51.12, 'Longitude':106.33}, #gusinoe
                        'PJD2':{'Latitude':45.05,'Longitude':-78.73}, #boshkung
                        'PJD31':{'Latitude':46.159,'Longitude':-78.105}, #storey
                        'RA3':{'Latitude':53.16, 'Longitude':13.03}, # Stechlinsee
                        'RAA4':{'Latitude':45.00, 'Longitude':-87.62}, # green bay at menominee
                        'RAA5':{'Latitude':43.63,'Longitude':-79.45}, # toronto harbour
                        'RA2':{'Latitude':53.13,'Longitude':12.99}, #nehmitzsee
                        'TB01':{'Longitude':18.58}, # Erken
                        }
    # read in LIAG lakes that already have corrected coordinates
    dfoo = pd.read_csv('../data/LakeCharacteristics/updatedCoordinates.csv')
    for i,row in dfoo.iterrows():
        if row.lakecode not in liag_corrections:
            liag_corrections[row.lakecode] = {'Latitude':round(row.lake_lat_dd,3),
                                              'Longitude':round(row.lake_lon_dd,3)}
                                              
    if 'lakecode' in df.columns:
        for key,value in liag_corrections.items():
            ind = df.lakecode.str.strip() == key
            for k,v in value.items():
                df.loc[ind,k.lower()] = v
    
    
    
    # SUWA latitude is incorrect
    #ind = df.lakename.astype(str).str.lower().str.contains('suwa') #& (df.latitude==36.15)
    #df.loc[ind,'latitude'] = 36.04
    
    # GTB is a bit south (but this doesn't get saved as it is overwritten by other data)
    #ind = df.lakename.astype(str).str.lower().str.contains('grand traverse bay') # was 44.75
    #df.loc[ind, 'latitude'] = 44.77


    ####################
    # 5. Dale Robertson 2019.5 data
    ####################
    if 'lake' in df.columns:
        ind = (df.Contributor=='Dale Robertson') & (df['Updated Year'] == 2019.5) & df.lake.isin(['Mendota','Geneva'])

        for c in ['Freeze Date','Freeze', 'Breakup Date', 'Final Break Up']:
            cmonth = '{} Month'.format(c)
            cday = '{} Day'.format(c)
            if cmonth not in df.columns:
                continue
            ind2 = ~df[cmonth].isnull()
            if 'Freeze' in c:
                finalcolumn = 'Freeze Date'
            else:
                finalcolumn = 'Final Breakup Date'
            df.loc[ind & ind2, finalcolumn] = df[ind&ind2].apply(lambda x: pd.to_datetime('{}/{}/2004'.format(
                                                        int(x[cmonth]), 
                                                        int(x[cday]))).strftime('%b %d')
                                                             if str(x[cmonth]).replace('.0','').isdigit()
                                                             else np.nan, axis=1)
    ##################
    # 6. Remove Danube
    ##################
    if 'lake' in df.columns:
        ind = df.lake == 'Danube'
        df = df[~ind].copy()
    
    ##################
    # 7. Fix Swiss lakes coordinates
    ##################
        ind = df['lake'] == 'Murtensee'
        df.loc[ind,'Latitude'] = 46.9276
        ind = df['lake'] == 'Sarnersee'
        df.loc[ind,'Latitude'] = 46.8698

    return df

def julian_day_to_date(df, julian_data):

    for key,value in julian_data.items():
        #print(key)
        if 'contributor' in value:
            contributor = value['contributor']
        else:
            contributor = ''
        jan1 = 1
        dy = 1
        
        if 'jan1' in value:
            jan1 = value['jan1']
        if 'dy' in value:
            dy = value['dy']
            
        if value['column'] not in df.columns:
            continue
            
        if value['finalcolumn'] in df.columns:
            ind = (~df[value['column']].isnull() & df[value['finalcolumn']].isnull() & 
                df['Contributor'].str.contains(contributor))
        else:
            ind = (~df[value['column']].isnull() & 
                df['Contributor'].str.contains(contributor))
      
        if 'nofreezeindicator' in value:
            df.loc[ind,value['finalcolumn']] = df.loc[ind,:].apply(lambda x: 
                                                                       doy_to_date(x[value['column']],
                                                                                  year=x[value['year']]+dy, jan1=jan1)
                                                                      if (x[value['column']]!=value['nofreezeindicator'])
                                                                      else 0, 
                                                                      axis=1)
            #display(dfcopy[ind].dropna(how='all',axis=1).head())
        elif 'missingdata' in value:
            df.loc[ind,value['finalcolumn']] = df.loc[ind,:].apply(lambda x: 
                                                                       doy_to_date(x[value['column']],
                                                                                  year=x[value['year']]+dy, jan1=jan1)
                                                                      if (x[value['column']]!=value['missingdata'][0]) & (x[value['column']]!=value['missingdata'][1])
                                                                      else x[value['column']], 
                                                                      axis=1)
            #display(dfcopy[ind].dropna(how='all',axis=1).head())
        else:
            #display(dfcopy[ind].dropna(how='all',axis=1).head())
            #display(dfcopy.loc[ind,value['column']].values)
            df.loc[ind,value['finalcolumn']] = df.loc[ind,:].apply(lambda x: 
                                                                       doy_to_date(x[value['column']],
                                                                                  year=x[value['year']]+dy, 
                                                                                  jan1=jan1)
                                                                           if not isinstance(x[value['column']],str)
                                                                           else np.nan,                                                             
                                                                      axis=1)
            #display(dfcopy[ind].dropna(how='all',axis=1).head())
    return df

def create_common_column_headers(df, config):
    """
    Finds all columns: ice on, ice off, season, duration, froze(Y or N)
                        city, state,
                        start_year, lake
    """
    iceoffcolumns = ['Final Breakup Date'] # start with this, as defined above for Dale Robertson lakes
    for c in df.columns:
        cc = str(c).lower()
        if (np.any([i in cc for i in ['off','thaw','out','melting',#'datelastice',#'datefirstopen',
                                        'first boat','break','broken','opened']])
                and np.all([i not in cc for i in ['julian','doy','source',
                                                  'final','breakup date day','breakup date month','breakup date year',
                                                  'middle break up month','middle break up day',
                                                  #'start',
                                                  'yriceday','iceoffdoy','xx',
                                                 'iceoff_day','iceoff_month','iceoff_year',
                                                 'thaw date 1.1','thaw date 1 old']])):
            iceoffcolumns.append(c)
    
    iceoncolumns = []
    for c in df.columns:
        cc = str(c).lower()
        if (np.any([i in cc for i in ['ice on','ice up','freesing',#'datefirstice',
                                      'freeze', 'date frozen', 'ice_on','ice_in',
                                      'iceon','last boat','cover_on','froze over','ice-on','ice in','closed']])
                and np.all([i not in cc for i in ['freeze day','freeze month','freeze date day','freeze date month',
                                                  'freeze date year','xx',
                                                  'year freeze up', 'source', 
                                                  'start', 'iceondoy','freezeupdoy',
                                                  #'final',
                                                  'yriceday',
                                                  '# days closed','iceon_doy',
                                                 'iceon_day','iceon_month','iceon_year',
                                                 'freeze date 1.1','freeze date 1 old']])):
            iceoncolumns.append(c)
    
    seasoncolumns = []
    for c in df.columns:
        if any([(i in str(c).lower()) & ('notes' not in str(c).lower()) &
                ('frozen' not in str(c).lower()) & ('spring' not in str(c).lower())
                for i in ['season','year','winter','old']]):
            seasoncolumns = seasoncolumns+[c]

    #iceoffcolumns = [i for i in iceoffcolumns if i not in 
    #                 ['iceoff_day','iceoff_month','iceoff_year',
    #                  'Thaw date 1.1','Thaw date 1 OLD']]
    #iceoncolumns = [i for i in iceoncolumns if i not in 
    #                ['iceon_day','iceon_month','iceon_year',
    #                 'Freeze date 1.1','Freeze date 1 OLD']]
    seasoncolumns = [i for i in seasoncolumns if i not in ['Updated Year','Winter_y','season',
                                                            'Day of the year',
                                                           'Thaw date 1 OLD','Water Year','Year','year',
                                                           'Freeze date 1 OLD','iceon_year','iceoff_year']]+['season','iceoff_year']


    new_dict = {'NEWice_off'  : iceoffcolumns,
                'NEWice_on'   : iceoncolumns,
                'NEWstate'   : ['State','state'],
                #'NEWcounty'  : ['County'],
                'NEWcity'    : ['TOWN','city'],
                #'start_year' : seasoncolumns,
                'NEWlake'   : ['lake','Lake','LAKE','ID number','Name','lakeid',
                               'Namn','Lake Finder ID','sta_name_s','lakename','lakes'],
                'NEWduration': ['# Days Frozen', '# days closed', 'COVER',
                                'DAYS', 'Duration (Days)', 'Ice duration', 
                                'IceDurCalc','duration','c','Icedays','Ice days',
                                'ice_cover_days','ice_duration',
                                'total days of ice cover','Ice cov [days]','Frozen'],
                'NEWfrozeYN': ['Lake_Froze_Y_N','froze','ice']
               }
    springyears = ['Water Year','Winter_y','Spring Year']

    df['NEWstart_year'] = np.nan
    for c in seasoncolumns:
        if c not in df.columns:
            continue
        ind = (~df[c].isnull()) & (df[c].astype(str)!='') & df['NEWstart_year'].isnull()
        #if df.loc[ind,'Contributor'].isin(['LIAG']).any():
        #    display(c)
        df.loc[ind, 'NEWstart_year'] = df.loc[ind,c].apply(lambda x: str(x).split('-')[0].split('–')[0])
    for c in springyears:
        if c not in df.columns:
            continue
        ind = ~df[c].isnull() & (df[c].astype(str)!='') & df['NEWstart_year'].isnull()
        df.loc[ind,'NEWstart_year'] = df.loc[ind,c].apply(lambda x: int(x)-1 if ('/' not in str(x)) else x.split('/')[0])
    # These are empty rows containing notes only (Hamilton and Yao)
    ind = df.NEWstart_year.isnull() | df.NEWstart_year.astype(str).str.contains('Lake|Sources')
    df = df.loc[~ind].copy()
    # remove and replace  ditto mark
    if 'Closed' in df.columns:
        ind = ~df.NEWstart_year.astype(str).str.contains("0|1|2|3|4|5|6|7|8|9") & ~df.Closed.isnull()
    
        df.loc[ind, 'NEWstart_year'] = df.loc[ind,'Closed'].apply(lambda x:
                                                                   x.year
                                                                       if x.month > 8 
                                                                       else
                                                                   x.year-1
                                                                  )
    ind = ~df.NEWstart_year.astype(str).str.contains("0|1|2|3|4|5|6|7|8|9")
    print('Removing rows.')     
    print(df.loc[ind,['Updated Year','NEWstart_year']])
    df = df[~ind]                                    
    # split seasons to get start-year
    df.loc[:,'NEWstart_year'] = df['NEWstart_year'].apply(lambda x: x.split('/')[0].split('-')[0] if isinstance(x,str) else int(x))

    ind = ~df.NEWstart_year.astype(str).str.replace('.','').str.strip().str.isdigit()

    df = df[~ind].copy()
    
    # POSTCARD DATA ISSUES
    # Adjust NEWstart_year if it is between 00 and 30:
    ind = df.NEWstart_year.astype(float).astype(int) < 30
    df.loc[ind, 'NEWstart_year'] = df.loc[ind, 'NEWstart_year'].astype(float).astype(int) + 2000
    ind = df.NEWstart_year.astype(float).astype(int) < 100
    df.loc[ind,'NEWstart_year'] = df.loc[ind, 'NEWstart_year'].astype(float).astype(int) + 1900
    
    
    # create new columns
    for key, values in new_dict.items():
        #print (key)
        keysnotes = '{} column'.format(key)
        df.loc[:, key] =  None
        df.loc[:, keysnotes] = None
        for v in values:
            if v in df.columns:
                ind =  [c is None for c in df.loc[:,key]] & ~df.loc[:,v].isnull()
            else:
                continue
            df.loc[ind,keysnotes] = v
            try:
                df.loc[ind,key] = df.loc[ind,v].astype(str).values
            except:
                print (key, v, 'PROBLEMS ')
                print (dfworking.loc[ind,v])
                df.loc[ind,key] = df.loc[ind,v].astype(str)
        #display(df_ts_working[values].dropna(thresh=1).dropna(how='all',axis=1))
    
    # Clean up NEWduration column
    df.NEWduration = df.NEWduration.astype(str).replace(
        ' ','nan').replace(
        'None','nan').replace(
        '---','nan').replace(
        '--','nan').replace(
        '-','nan').astype(float)
        
        
    # update lake names, merging with MN lakes and adding 'lat', 'long' columns
    df = update_lake_names(df, config)

    # clean up latitude and longitude columns
    latitudeCols = ['lat','latitude','Latitude','rep_latitude_fl']
    longitudeCols= ['long','longitude','Longitude','rep_longitude_fl']
    df['NEWlatitude'] = np.nan
    df['NEWlongitude'] = np.nan
    for l in latitudeCols:
        if l not in df.columns:
            continue
        ind = df['NEWlatitude'].isnull() & ~df[l].isnull() & ~df[l].astype(str).str.contains('999')
        if ind.sum() > 0:
            print (l, ind.sum())
        df.loc[ind, 'NEWlatitude'] = df.loc[ind,l].apply(lambda x: float(x.replace(',','.')) if isinstance(x,str) else float(x))
    for l in longitudeCols:
        if l not in df.columns:
            continue
        ind = df['NEWlongitude'].isnull() & ~df[l].isnull() & ~df[l].astype(str).str.contains('999')
        if ind.sum() > 0:
            print (l, ind.sum())
        df.loc[ind, 'NEWlongitude'] = df.loc[ind,l].apply(lambda x: float(x.replace(',','.')) if isinstance(x,str) else float(x))

    return df
    
    
def fix_typos(df, config):

    iceonoff_typos = eval(config.get('CORRECTIONS','iceon_off'))
    iceonoff_char_typos = eval(config.get('CORRECTIONS','iceon_off_char'))
    # replace these with -999
    iceonoff_missing = eval(config.get('CORRECTIONS','iceon_off_missing'))
    
    year_typos = eval(config.get('CORRECTIONS','year'))
    
    df.NEWice_off = df.NEWice_off.replace(iceonoff_typos)
    df.NEWice_on = df.NEWice_on.replace(iceonoff_typos)
    for key,value in iceonoff_char_typos.items():
        df.NEWice_off = df.NEWice_off.astype(str).str.replace(key,value)
        df.NEWice_on = df.NEWice_on.astype(str).str.replace(key,value)
    
    # this should be more efficient than running through all key,value as above
    ind = df.NEWice_off.astype(str).str.contains('|'.join(iceonoff_missing.keys()))
    df.loc[ind,'NEWice_off'] = '-999'
    ind = df.NEWice_on.astype(str).str.contains('|'.join(iceonoff_missing.keys()))
    df.loc[ind,'NEWice_on'] = '-999'
    
    df.NEWstart_year = df.NEWstart_year.replace(year_typos)
    
    return df
   

def determine_icefree_years(df, logfile=None):

    nofreezetext = ['no ice','Never Froze','pas de gel','did not freeze',
    # postcard data additions
     'No freeze this winter','Main basin never froze', 'No complete ice cover', 'no complete freeze',
     'no complete ice','No Freeze','No full ice cover','No full freeze', 'Only 1/4 covered', 'No complete cover']
    
    df.NEWfrozeYN = df.NEWfrozeYN.replace(u'1.0',u'Y').replace(u'0.0',u'N').replace('open','N').replace('froze','Y')
    
    # invert no.ice to be ice (i.e., no.ice=1 means ice='N')
    if 'no.ice' in df.columns:
        ind = df.NEWfrozeYN.isnull() & ~df['no.ice'].isnull()
        df.loc[ind,'NEWfrozeYN'] = df.loc[ind,'no.ice'].replace(1.,u'N').replace(0.,u'Y')
        df.loc[ind,'NEWfrozeYN column'] = 'no.ice'
    
    
    ind = ((df.NEWduration==0.) | (df.NEWfrozeYN =='N') | 
       ## From Hodgkins
       (df.NEWice_off=='999.0') | 
       # Randsfjorden and Gull
       (df.NEWice_off == '0') | (df.NEWice_on == '0') |
        df.NEWice_on.str.contains('|'.join(nofreezetext)) | df.NEWice_off.str.contains('|'.join(nofreezetext)))

    if logfile is not None:
        logfile.write('===================================\n')
        logfile.write('Lakes with Recorded Ice-Free Events\n\t')
        logfile.write( '\n\t'.join(df.loc[ind,'NEWlake'].unique() )+'\n')
    #display(group.dropna(how='all',axis=1))
    #print group.NEWduration.unique(), group.NEWfrozeYN.unique()

    df.loc[ind, 'NEWice_off'] = 0
    df.loc[ind, 'NEWice_on'] = 0
    df.loc[ind, 'NEWduration'] = 0.
    df.loc[ind, 'NEWfrozeYN'] = 'N'
    
    # now fill in 'Y' for lakes with a duration
    ind = (df.NEWduration>0) & ~df.NEWduration.isnull()
    df.loc[ind, 'NEWfrozeYN'] = 'Y'

    
    return df

def split_iceon_iceoff(df):
    c = 'NEWice_off'
    ind = df[c]
    
    
    'NEWice_on'

def reformat_iceon_iceoff(df):
    
    dfIOnOff = pd.DataFrame()
    dfIOnOff['IOff'] = df.NEWice_off.astype(str) 
    dfIOnOff['IOn'] = df.NEWice_on.astype(str) 
    dfIOnOff['NEWstart_year'] = df.NEWstart_year.astype(float).astype(int)

    df.loc[:, 'ice_off_new'] = dfIOnOff.apply(lambda x: date_conversion(x.IOff, year=x.NEWstart_year),axis=1)
    df.loc[:, 'ice_on_new'] = dfIOnOff.apply(lambda x: date_conversion(x.IOn, year=x.NEWstart_year),axis=1)
    
    return df
    
def update_lake_names(df, config):
    # Consider moving this to the config_lakeiceTS.ini file
    vowel_convert = {
        u'\xc5':'A',
        u'\xc4':'A',
        u'\xc6':'AE',
        u'\xd6':'O',
        u'\xd8':'O',
        u'\xe4':'a',
        u'\xe5':'a',
        u'\xe6':'ae',
        u'\xf6':'o',
        u'\xf8':'o',
        u'\xc3\x84':'A',
        u'\xc3\x85':'A',
        u'\xc3\xa4':'a',
        u'\xc3\x96':'O',
        u'\xc3\xb6':'o',
    }
    # Minnesota lake names
    MNfilename = '../data/Updated Data/Ken Blumenfeld:Pete Boulay/lake_ice_id_spreadsheet.xlsx'
    dfMN = pd.read_excel(MNfilename)
    dfMN['dow num'] = dfMN['dow num'].astype(str)
    
    if 'ID number' in df.columns:
        indMNlakes = ~df['ID number'].isnull()
        print('{} MN lakes'.format(indMNlakes.sum()))
    #for ffx in df.loc[indMNlakes,'ID number'].unique():
    #    print(ffx)
    #for c in df.columns:
    #    print(c)
        df.loc[indMNlakes, 'MN ID']=df.loc[indMNlakes, 'ID number'].apply(lambda x: str(x).split('.')[0])
    #for c in df.columns:
    #    print(c)
    #print(df.shape)
        df = df.merge(dfMN[['dow num','name','lat','long',
                           'acres','perimeter','area of basin',
                    'class ','wettype char.']],left_on='MN ID',right_on='dow num', 
                    validate='many_to_one',how='left')
    #print(df.shape)
    #for c in df.columns:
    #   print(c)
    #print('{} MN lakes 1 '.format(indMNlakes.sum()))
        ind = ~df['ID number'].isnull() & ~df['name'].isnull()
    #print('{}'.format(ind.sum()))
        df.loc[ind, 'NEWlake'] = df.loc[ind,:].apply(lambda row: '{} (MN{})'.format(row['name'], row['MN ID']),axis=1)
    
    #df.loc[indMNlakes & df['name'].isnull(), 'NEWlake'] = df.loc[indMNlakes &  df['name'].isnull(),:].apply(lambda row: 'Unmatched lake (MN{})'.format(row['MN ID']), axis=1)
        ind = ~df['ID number'].isnull() & df['name'].isnull()
    #print('{}'.format(ind.sum()))
        df.loc[ind, 'NEWlake'] = df.loc[ind,:].apply(lambda row: 'MN{}'.format(row['MN ID']), axis=1)
    #print('{} MN lakes 2 '.format(indMNlakes.sum()))
    
    #print('{} MN lakes 3'.format((~df['ID number'].isnull()).sum()))
    
    #print('WITHIN FUNCTION')
    #ind = df.Contributor.str.contains('Boulay') & ~df.NEWlake.astype(str).str.contains('MN')
    #ind = indMNlakes & ~df.NEWlake.astype(str).str.contains('MN')
    #print('{}'.format(ind.sum()))
    #ind = ~df['ID number'].isnull() & ~df.NEWlake.astype(str).str.contains('MN')
    #print('{}'.format(ind.sum()))
    
    #print(df.loc[ind, ['NEWlake', 'name', 'MN ID', 'ID number']].values)
    #print(df.loc[ind,:].apply(lambda row: '{} (MN{})'.format(row['name'], row['MN ID']),axis=1))
    #ind = df.Contributor.str.contains('Boulay') & df.NEWlake.astype(str).str.contains('MN')
    #print('{}'.format(ind.sum()))
    #print(df.loc[ind, ['NEWlake','FileName','ID number', 'MN ID','name']].values)
    
    #print(df.loc[indMNlakes & ~df.NEWlake.astype(str).str.contains('MN'), 'NEWlake'].values)
    # REPLACE LTER lake abbreviations with full lake name
    lake_dict = eval(config.get('CORRECTIONS','lake_names_lter'))
    ind = df.NEWlake.isin(lake_dict.keys()) & (df.Contributor=='LTER')
    df.loc[ind,'NEWlake'] = df.loc[ind,'NEWlake'].replace(lake_dict)
    
    # go back on MN lakes, removing Unmatched lake
    #df.loc[df['NEWlake'].str.contains('Unmatched lake'), 'NEWlake'] = df.loc[df['NEWlake'].str.contains('Unmatched lake'), 'NEWlake'].apply(lambda x: x.split()[-1].strip('()').strip())
    
    if (df['NEWlake'].isnull()).sum()>0:
        print('Missing lake name. Forward filling.')
        print(df.loc[df['NEWlake'].isnull(),['FileName','NEWstart_year']])
        df.NEWlake = df.NEWlake.ffill()
        
    #ind = df['NEWlake'].str.contains('Unmatched lake')
    #print('Unmatched MN lakes: {}'.format(ind.sum()))
    #df.loc[ind, 'NEWlake'] = df.loc[ind, 'NEWlake'].apply(lambda x: x.split()[-1].strip('()').strip())

    lake_dict = eval(config.get('CORRECTIONS','lake_names_other'))
    df.NEWlake = df.NEWlake.replace(lake_dict)
    
    # THIS SHOULD BE MOVED SOMEWHERE ELSE
    if 'Country' in df.columns:
        df.loc[(df.NEWlake=='GULL LAKE') & (df.Contributor=='Kevin Blagrave') & df.Country.isnull(),'Country'] = 'UNITED STATES'

    # Replace accents and umlauts with closest equivalent non-accented character
    df['NEWlake_english'] = df.NEWlake
    
    for key,value in vowel_convert.items():
        df['NEWlake_english'] = df.NEWlake_english.str.replace(key,value)
    
    return df
    

def assign_lakecodes(dforig, config):
    df = dforig.copy()
    # Consider running this once separately and when new lakes are added in the future ask user for a new lakecode.
    # creating a nice dictionary of lakecodes and lakenames, city, country, contributors (is that enough info?)
    liag_lakecodes_file = config.get('FILES','liag_lakecode')
    other_lakecodes_file = config.get('FILES','other_lakecode')
    df1 = pd.read_csv(liag_lakecodes_file,encoding='utf-8')
    df2 = pd.read_csv(other_lakecodes_file,encoding='utf-8')
    
    #liag_corrections = {'ARAI1':{'Latitude':36.04}, # ARAK1, YATSU1 and WSTA1 are all still 36.15
                        #'RA2':{'Latitude':53.13,'Longitude':12.99}, # Nehmitzsee
                        #'TB01':{'Longitude':18.58}, # Erken
     #                   'RAA3' :{'Latitude':44.77} # Grand Traverse Bay
     #                   }
    #manually went through these lakes and assigned new coordinates in water
    # these only 
    liag_corrections = {
                        'ARAI1':{'Latitude':36.04}, 
                        'RAA3' :{'Latitude':44.77}, # Grand Traverse Bay                       
                        'ARAK1':{'Latitude':36.04},
                        'WSTA1':{'Latitude':36.04},
                        'YATSU1':{'Latitude':36.04},
                        'ETJ1':{'Latitude':46.171,'Longitude':-89.344}, # anderson
                        'JJM11':{'Latitude':45.754,'Longitude':-91.651}, #long
                        'JJM19':{'Latitude':46.057,'Longitude':-89.566}, # mystery
                        'JJM23':{'Latitude':46.053,'Longitude':-89.567}, # spruce
                        'JJM25':{'Latitude':44.33,'Longitude':-88.634}, # black otter
                        'MINN37':{'Latitude':44.555, 'Longitude':-92.433}, # pepin
                        'NG2':{'Latitude':51.12, 'Longitude':106.33}, #gusinoe
                        'PJD2':{'Latitude':45.05,'Longitude':-78.73}, #boshkung
                        'PJD31':{'Latitude':46.159,'Longitude':-78.105}, #storey
                        'RA3':{'Latitude':53.16, 'Longitude':13.03}, # Stechlinsee
                        'RAA4':{'Latitude':45.00, 'Longitude':-87.62}, # green bay at menominee
                        'RAA5':{'Latitude':43.63,'Longitude':-79.45}, # toronto harbour
                        }
    # read in LIAG lakes that already have corrected coordinates
    dfoo = pd.read_csv('../data/LakeCharacteristics/updatedCoordinates.csv')
    for i,row in dfoo.iterrows():
        if row.lakecode not in liag_corrections:
            liag_corrections[row.lakecode] = {'Latitude':round(row.lake_lat_dd,3),
                                              'Longitude':round(row.lake_lon_dd,3)}
                                              
    #for key,value in liag_corrections.items():
    #    ind = df.lakecode.str.strip() == key
    #    for k,v in value.items():
    #        df.loc[ind,k.lower()] = v
    
    #for key,value in liag_corrections.items():
    #    for k,v in value.items():
    #        df1.loc[df1.lakecode==key,k] = v

    df1 = df1.append(df2,ignore_index=True)
    dflakecodes = df1[['lakecode_y','Latitude','Longitude','lakes','lakes_english','contributor_new','source_new','city','state','Country']].drop_duplicates()
    
    # Assign new latitude and longitudes to dflakecodes
    for key,value in liag_corrections.items():
        for k,v in value.items():
            dflakecodes.loc[dflakecodes.lakecode_y==key,k] = v
    
    for c in ['lakes', 'lakes_english','contributor_new','source_new','lakecode_y','Country']:
        dflakecodes[c] = dflakecodes[c].str.strip()
    
    # Match lakecodes -- exclude PostCard Data from this matching

    for i,row in df[df.lakecode.isnull() & (~df['Contributor'].isin(['LakeIceData','Data from Contributors_2021','Postcard Data']))].drop_duplicates(subset=['Updated Year','NEWlake_english','Contributor','NEWcity','source']).iterrows():

        dflc = dflakecodes.drop_duplicates(subset=['lakecode_y','contributor_new',
                                               'city','Country','lakes_english',
                                               'Latitude','Longitude'])

        # try to match solely on lake name and contributor
        if row['Updated Year'] <= 2019:
            ind = (dflc.lakes_english == row.NEWlake_english)
        else:
            ind = (dflc.lakes_english == row.NEWlake_english) & (dflc.contributor_new == row.Contributor)
        #if row.NEWlake_english=='Monona':
        #    print('MONONA', row, ind.sum())
        # if there is no match on lake name & contributor
        if ind.sum()==0:
            if row.Contributor!='Johanna Korhonen':
                print('no match on lakename alone', row.NEWlake_english, row.Contributor, row.source)
                print('   .... being added to dflakecodes. Will have to manually add lakecode')
                dflakecodes = dflakecodes.append(pd.DataFrame({'lakes_english':[row.NEWlake_english],
                                                 'city':[row.NEWcity],
                                                 'source':[row.source],
                                                 'lakecode_y':[np.nan],
                                                 'Latitude':[np.nan],
                                                 'Longitude':[np.nan],
                                                 'contributor_new':[row.Contributor]}),ignore_index=True)
                continue
            else:
                # if contributor is Korhonen, continue since this is expected for numbered lakes
                continue
        elif ind.sum() > 1:
            # try lake name and contributor
            ind = ((dflc.lakes_english == row.NEWlake_english) & 
                (dflc.contributor_new == row.Contributor))
            if ind.sum()==0:
                ind = (dflc.lakes_english == row.NEWlake_english) & (dflc.Country==row.Country)
                if ind.sum() != 1:
                    print('PROBLEM with matching country/lakename', row.NEWlake_english,row.Contributor, row.source,row.Country)
                    print('   .... being added to dflakecodes. Will have to manually add lakecode')
                    dflakecodes = dflakecodes.append(pd.DataFrame({'lakes_english':[row.NEWlake_english],
                                                 'city':[row.NEWcity],
                                                 'source':[row.source],
                                                 'lakecode_y':[np.nan],
                                                 'Latitude':[np.nan],
                                                 'Longitude':[np.nan],
                                                 'contributor_new':[row.Contributor]}),ignore_index=True)
                    continue
                    #display(dflakecodes[dflakecodes.lakes_english==row.NEWlake_english])
            elif ind.sum() > 1:
                # try to limit by including city too
                ind = ((dflc.lakes_english == row.NEWlake_english) & 
                       (dflc.contributor_new == row.Contributor) & 
                       (dflc.city == row.NEWcity))
    #                   ((dflc.source==row.source) | ((dflc.source.isnull() & np.isnan(row.source))))
                if ind.sum()==0:
                    print('PROBLEM 2', row.NEWlake_english,row.Contributor, row.source, row.NEWcity)
                    ind = ((dflc.lakes_english == row.NEWlake_english) & 
                       (dflc.contributor_new == row.Contributor))
                    print('duplicates... Can not match on city. Have to MANUALLY DO SOMETHING')
                    display(dflc[ind])
                    #print(row.Contributor,row.NEWlake_english, row.NEWcity)
                    #dflc.city.apply(lambda x: similar(x, row.NEWcity)
                    raw_ind = dflc[~dflc.city.isnull()].city.apply(lambda x: similar(x, 'Eagle Lake')).idxmax()
                    print ('Guess: ',raw_ind)
                    #raw_ind = input('Which index matches: {},{},{}'.format(row.Contributor,row.NEWlake_english, row.NEWcity))
                    #print(dflc.index.values)
                    ind = dflc.index.values==int(raw_ind)
                    lakecodefoo,latitudefoo,longitudefoo = dflc.loc[ind,['lakecode_y','Latitude','Longitude']].values[0].tolist()                
                    dflakecodes= dflakecodes.append(pd.DataFrame({'lakes_english':[row.NEWlake_english],
                                                 'city':[row.NEWcity],
                                                 'source':[row.source],
                                                 'lakecode_y':[lakecodefoo],
                                                 'Latitude':[latitudefoo],
                                                 'Longitude':[longitudefoo],
                                                 'contributor_new':[row.Contributor]}),ignore_index=True)
                elif ind.sum() > 1:
                    print('duplicates... Too many matches on city. Have to MANUALLY DO SOMETHING')
                    display(dflc[ind])
                    print(row.Contributor,row.NEWlake_english, row.NEWcity)
                    raw_ind = input('Which index?')
                    print(dflc.index.values)
                    ind = dflc.index.values==int(raw_ind)
        #print (ind)
        if ind.sum()!=1:
            print('PROBLEM !!!!')
            #break
        lakecode, latitude, longitude = dflc.loc[ind, ['lakecode_y','Latitude','Longitude']].values[0]
        if isinstance(lakecode,float):
            print('PROBLEM', lakecode, latitude, longitude, row.NEWlake_english)
        #print(i, lakecode, latitude, longitude)

    #    df.loc[i, 'lakecode'] = lakecode
    #    if np.isnan(df.loc[i, 'NEWlatitude']):
    #        df.loc[i,'NEWlatitude'] = latitude
    #    if np.isnan(df.loc[i, 'NEWlongitude']):
    #        df.loc[i, 'NEWlongitude'] = longitude
    
    # fill in NEW LAKES
    newlakecodes = eval(config.get('LAKECODES','newlakecodes'))

    # key is Lake Name
    # value contains lakecode, and potentially latitude, longitude, country
    for key,value in newlakecodes.items():
        # exact match
        ind = dflakecodes.lakes_english.str.lower() == key.lower()
        # if no exact match, try 'contains'
        if ind.sum()==0:
            ind = dflakecodes.lakes_english.str.lower().str.contains(key.lower())
        dflakecodes.loc[ind, 'lakes'] = key
        dflakecodes.loc[ind, 'lakecode_y'] = value['lakecode']
        for cc in ['country','latitude','longitude']:
            if cc in value:
                print(key,value,cc.title())
                dflakecodes.loc[ind,cc.title()]=value[cc]
            else:
            # assume otherwise that lat, lon or country already exist in original
                newvalue = df.loc[df.NEWlake_english==key, cc.title()].dropna().unique()
                if len(newvalue)== 0:
                    newvalue = df.loc[df.NEWlake_english==key, cc].dropna().unique()
                print(key, cc.title(), newvalue)
                if len(newvalue)>0:
                    dflakecodes.loc[ind,cc.title()] = newvalue[0]
                else:
                    dflakecodes.loc[ind,cc.title()] = np.nan
    """
    ind = dflakecodes.lakes_english.str.lower().str.contains('joux')
    dflakecodes.loc[ind,'Latitude'] = 46.638
    dflakecodes.loc[ind,'Longitude'] = 6.284
    dflakecodes.loc[ind,'lakecode_y'] = 'xJDM01'
    dflakecodes.loc[ind,'Country'] = 'Switzerland'
    dflakecodes.loc[ind,'lakes'] = 'Lac de Joux'

    ind = dflakecodes.lakes_english.str.lower().str.contains('kempenfelt bay')
    dflakecodes.loc[ind,'Latitude'] = 44.386
    dflakecodes.loc[ind,'Longitude'] = -79.614
    dflakecodes.loc[ind,'lakecode_y'] = 'xAM01'
    dflakecodes.loc[ind,'Country'] = 'Canada'
    dflakecodes.loc[ind,'lakes'] = 'Kempenfelt Bay'
    
    ind = dflakecodes.lakes_english.str.lower().str.contains('lake serwvy')
    dflakecodes.loc[ind,'Latitude'] = 53.901
    dflakecodes.loc[ind,'Longitude'] = 23.206
    dflakecodes.loc[ind,'lakecode_y'] = 'xIMGW01'
    dflakecodes.loc[ind,'Country'] = 'Poland'
    dflakecodes.loc[ind,'lakes'] = 'Lake Serwy'
    """
    # Danube is RIVER, plus has multiple sites so would have to assign different
    #   lakecodes for each different site (under the 'Event' column of the original file)
    #ind = dflakecodes.lakes_english.str.lower().str.contains('danube')
    #dflakecodes.loc[ind,'Latitude'] = 45.9927
    #dflakecodes.loc[ind,'Longitude'] = 18.6945
    #dflakecodes.loc[ind,'lakecode_y'] = 'xTAK02'
    #dflakecodes.loc[ind,'Country'] = 'Hungary'
    #dflakecodes.loc[ind,'lakes'] = 'Danube'

    matchlakecodes = eval(config.get('LAKECODES','matchlakecodes'))
    
    for key,value in matchlakecodes.items():
        ind = dflakecodes.lakecode_y==value
        lc,lat,lon,country = dflakecodes[ind].drop_duplicates(['Latitude','Longitude'])[['lakecode_y','Latitude','Longitude','Country']].values[0]
        ind = (dflakecodes.lakes_english==key) & (dflakecodes.lakecode_y.isnull())
        #print (key, ind.sum(), lat, lon)
        dflakecodes.loc[ind,'Latitude'] = lat
        dflakecodes.loc[ind, 'Longitude'] = lon
        dflakecodes.loc[ind, 'lakecode_y'] = lc
        dflakecodes.loc[ind, 'Country'] = country
        dflakecodes.loc[ind,'lakes'] = dflakecodes.loc[ind,'lakes_english']
    
    # extract list of all unique combinations of lake name, lat/lon, contributor, lakecode
    dflc = dflakecodes.drop_duplicates(subset=['lakecode_y','city',
                                               'contributor_new','lakes_english',
                                               'Latitude','Longitude'])
    
    # expect PROBLEM KORHONEN for numbered lakes (which are duplicates anyway)

    for i,row in df[df.lakecode.isnull()].drop_duplicates(subset=['NEWlake_english','Contributor','NEWcity','source']).iterrows():

    
        # try lake name first
        ind = (dflc.lakes_english == row.NEWlake_english) & (~dflc.lakecode_y.isnull())
        
        if row.NEWlake_english=='Monona':
            print("MONONA",ind.sum())
            display(dflc[ind])
        #if len(dflc[ind].drop_duplicates('lakecode_y'))==1:
        #    ind = ~dflc.lakecode_y.duplicated(keep='first') & (dflc.lakes_english == row.NEWlake_english)
            #print('LAKE NAME CHECK : SUM should be 1', ind.sum())
    
        if ind.sum()==0:
            if row.Contributor!='Johanna Korhonen':
                print('no match', row.NEWlake_english, row.Contributor, row.source)
                print('   .... adding to dflakecodes')
                dflakecodes = dflakecodes.append(pd.DataFrame({'lakes_english':[row.NEWlake_english],
                                                 'city':[row.NEWcity],
                                                 'source':[row.source],
                                                 'lakecode':[np.nan],
                                                 'Latitude':[np.nan],
                                                 'Longitude':[np.nan],
                                                 'contributor_new':[row.Contributor]}),ignore_index=True)
                continue
            else:
                if not (str(row.NEWlake_english)[0]).isdigit():
                    print('PROBLEM _ Korhonen', row.NEWlake_english)
                continue
        # JUNE 29 2020 ADDED "& (len(dflc....>1)"
        elif (ind.sum() > 1) & (len(dflc[ind].drop_duplicates(['lakecode_y','Latitude','Longitude']))>1):
            # try lake name and contributor
            ind = ((dflc.lakes_english == row.NEWlake_english) & 
                (dflc.contributor_new == row.Contributor))
            if ind.sum()==0:
                ind = (dflc.lakes_english == row.NEWlake_english) & (dflc.Country==row.Country)
                if ind.sum() != 1:
                    print('PROBLEM', row.NEWlake_english,row.Contributor, row.source,row.Country)
                    print('   .... adding to dflakecodes')
                    dflakecodes = dflakecodes.append(pd.DataFrame({'lakes_english':[row.NEWlake_english],
                                                 'city':[row.NEWcity],
                                                 'source':[row.source],
                                                 'lakecode':[np.nan],
                                                 'Latitude':[np.nan],
                                                 'Longitude':[np.nan],
                                                 'contributor_new':[row.Contributor]}),ignore_index=True)
                    continue
                    #display(dflakecodes[dflakecodes.lakes_english==row.NEWlake_english])
            elif ind.sum() > 1:
                ind = ((dflc.lakes_english == row.NEWlake_english) & 
                       (dflc.contributor_new == row.Contributor) & 
                       (dflc.city == row.NEWcity))
    #                   ((dflc.source==row.source) | ((dflc.source.isnull() & np.isnan(row.source))))
                if ind.sum()==0:
                    print('PROBLEM 2', row.NEWlake_english,row.Contributor, row.source)
                elif ind.sum() > 1:
                    print('duplicates... Have to MANUALLY DO SOMETHING')
                    display(dflc[ind])
                    print(row.Contributor,row.NEWlake_english, row.NEWcity)
                    raw_ind = input('Which index?')
                    print(dflc.index.values)
                    ind = dflc.index.values==int(raw_ind)
        #print (ind)
        lakecode, latitude, longitude = dflc.loc[ind, ['lakecode_y','Latitude','Longitude']].values[0]
        if len(dflc.loc[ind,['lakecode_y','Latitude','Longitude']].drop_duplicates()) != 1:
            print('PROBLEM, TOO MANY', i, lakecode, latitude, longitude)

        df.loc[i, 'lakecode'] = lakecode
        if np.isnan(df.loc[i, 'NEWlatitude']):
            df.loc[i,'NEWlatitude'] = latitude
        if np.isnan(df.loc[i, 'NEWlongitude']):
            df.loc[i, 'NEWlongitude'] = longitude
            
    groupbycolumns = ['NEWlake_english','Contributor','NEWcity','source']
    for gc in groupbycolumns:
        df[gc] = df[gc].fillna('-999')
    dfgroup = df.groupby(groupbycolumns, sort=False)
    for c in ['NEWlatitude','NEWlongitude','lakecode']:
        df[c] = dfgroup[c].apply(lambda x: x.ffill().bfill())
        print('DONE',c)
    
    return df
    
    
def merge_rows(df):
    #Prepare the data by removing duplicate rows and rows with no observations
    df = df.drop_duplicates()
    df = df[~(df.ice_on_new.astype(str).str.contains('-999') & df.NEWfrozeYN.isnull()
          & df.ice_off_new.astype(str).str.contains('-999'))].copy()
    
    ### STEP ONE. Merge multiple freeze/thaw cycles into one row.

    # extract rows with only one ice on
    indon = ~df.ice_on_new.astype(str).str.contains('-999')
    dfOn = df[indon].reset_index()
    dfOn = dfOn[~dfOn.duplicated(['FileName','NEWstart_year','lakecode','source'],keep=False)]
    dfOn = dfOn.set_index(['FileName','lakecode','source','NEWstart_year']).rename({'index':'ice_on_index'},axis=1)

    # extract rows with only one ice off
    indoff = ~df.ice_off_new.astype(str).str.contains('-999')
    dfOff = df[indoff].reset_index()
    dfOff = dfOff[~dfOff.duplicated(['FileName','NEWstart_year','lakecode','source'],keep=False)]
    dfOff = dfOff.set_index(['FileName','lakecode','source','NEWstart_year']).rename({'index':'ice_off_index'},axis=1)

    # merge into one dataframe
    dfOnOff = dfOn.loc[:,[c for c in dfOn.columns if c not in ['ice_off_new','ice_off_index']]].merge(
                dfOff[['ice_off_new','ice_off_index']],left_index=True,right_index=True,how='outer').reset_index()

    #dfcopy= df.copy()
    ind = (dfOnOff.ice_off_index!=dfOnOff.ice_on_index) & ~dfOnOff.ice_off_index.isnull() & ~dfOnOff.ice_on_index.isnull()
    indreplace = dfOnOff.loc[ind, 'ice_on_index']
    indremove = dfOnOff.loc[ind,'ice_off_index']

    # replace rows
    df.loc[indreplace.values, 'ice_off_new'] = dfOnOff.loc[ind,'ice_off_new'].values
    df.loc[indreplace.values, ['ice_on_new','ice_off_new']]

    # now remove rows
    df = df.drop(indremove.values)
    #dfcopy.loc[indreplace.values, ['ice_on_new','ice_off_new']]

    indMNlakes = df.FileName.str.contains('complete_ice_in_out_') 
    # Need to merge FileName IceWisconsinLongRecords5 and IceWisconsinLongRecords1

    df.FileName = df.FileName.str.replace('WisconsinLongRecords1','WisconsinLongRecords')
    df.FileName = df.FileName.str.replace('WisconsinLongRecords5','WisconsinLongRecords')

    indlist = []
    for name,group in df[~indMNlakes].groupby(['FileName','lakecode','NEWstart_year']):
        if len(group) >1:
            #print(name)
            #display(group.dropna(how='all',axis=1))
            firstind = group.dropna(how='all',axis=1).index[:1]
            otherind = group.dropna(how='all',axis=1).index[1:]

            iceons = list(set([l for l in group.ice_on_new.values if ('-999' not in str(l)) & (str(l)!='0')]))
            iceoffs = list(set([l for l in group.ice_off_new.values if ('-999' not in str(l)) & (str(l)!='0')]))

            dfoo = pd.DataFrame({'Date':iceons+iceoffs,'Event':['iceon']*len(iceons)+['iceoff']*len(iceoffs)})
            prEvent = None
            rep = 0
            dfoo = dfoo.sort_values('Date').replace({'iceon':0,'iceoff':1})
            if len(dfoo)==0:
                display(group.dropna(how='all',axis=1))
            for i,row in dfoo.iterrows():
                if (prEvent is None) | (row.Event==prEvent) | (row.Event==0):
                    rep = rep+1
                dfoo.loc[i,'Rep'] = rep
                prEvent = row.Event
            repEvents = dfoo.Rep.unique()
            repEvents = [1,2,3,4,5,6]
            reind = [(i,j) for i in repEvents for j in [0,1]]
            dfoo = dfoo.set_index(['Rep','Event']).reindex(reind).fillna('-999').reset_index()
            newvalues = {x:y for x,y in dfoo.apply(lambda x: ('ice_on_new_{}'.format(int(x.Rep)),x.Date) if x.Event==0 else
                              ('ice_off_new_{}'.format(int(x.Rep)),x.Date),axis=1).tolist()}
            indlist.append([(firstind,otherind,newvalues)])
            #for key,value in newvalues.items():
            #    dfcopy.loc[firstind,key] = value
            #dfcopy = dfcopy.drop(otherind)
            #if len(iceons)!=len(iceoffs):
            #    break


    # Run through MN lakes (including source as an additional unique identifier for given year)        
    for name,group in df[indMNlakes].groupby(['FileName','source','lakecode','NEWstart_year']):
        if len(group) >1:
            #print(name)
            #display(group.dropna(how='all',axis=1))
            #input('continue?')
            firstind = group.dropna(how='all',axis=1).index[:1]
            otherind = group.dropna(how='all',axis=1).index[1:]

            iceons = list(set([l for l in group.ice_on_new.values if ('-999' not in str(l)) & (str(l)!='0')]))
            iceoffs = list(set([l for l in group.ice_off_new.values if ('-999' not in str(l)) & (str(l)!='0')]))

            dfoo = pd.DataFrame({'Date':iceons+iceoffs,'Event':['iceon']*len(iceons)+['iceoff']*len(iceoffs)})
            prEvent = None
            rep = 0
            dfoo = dfoo.sort_values('Date').replace({'iceon':0,'iceoff':1})
            for i,row in dfoo.iterrows():
                if (prEvent is None) | (row.Event==prEvent) | (row.Event==0):
                    rep = rep+1
                dfoo.loc[i,'Rep'] = rep
                prEvent = row.Event
            #repEvents = dfoo.Rep.unique()
            repEvents = [1,2,3,4,5,6]
            reind = [(i,j) for i in repEvents for j in [0,1]]
            dfoo = dfoo.set_index(['Rep','Event']).reindex(reind).fillna('-999').reset_index()
            newvalues = {x:y for x,y in dfoo.apply(lambda x: ('ice_on_new_{}'.format(int(x.Rep)),x.Date) if x.Event==0 else
                              ('ice_off_new_{}'.format(int(x.Rep)),x.Date),axis=1).tolist()}
            indlist.append([(firstind,otherind,newvalues)])
            #for key,value in newvalues.items():
            #    dfcopy.loc[firstind,key] = value
            #dfcopy = dfcopy.drop(otherind)
            #if len(iceons)!=len(iceoffs):
            #    break
    # Sort results from above and apply to complete dataframe
    #dfcopy2 = dfcopy.copy()
    droplist= []
    keeplist=[]
    resultlist = []
    for i in indlist:
        for ii,jj,kk in i:
            droplist.extend(jj.values)
            keeplist.extend(ii.values)
            foo = []
            column_names = []
            for key,value in kk.items():
                foo.append(value)
                column_names.append(key)
            resultlist.append(foo)
    mydict = {}
    for i, j in zip(column_names, np.array(resultlist).transpose().tolist()):
        mydict[i] = j
    df = df.drop(droplist)
    df = df.merge(pd.DataFrame(mydict, index=keeplist),left_index=True, right_index=True, validate='one_to_one',how='left')
    indupdate = df.ice_on_new_1.isnull() & df.ice_off_new_1.isnull()

    df.loc[indupdate,'ice_on_new_1'] = df.loc[indupdate,'ice_on_new']
    df.loc[indupdate,'ice_off_new_1'] = df.loc[indupdate,'ice_off_new']

    return df
    
def remove_lakecode_startyear_duplicates(dfinput):

    df = dfinput[~dfinput.lakecode.isnull()].copy()   
    
    
    for c in ['_{}'.format(i) for i in range(1,7)]:
        df.loc[:,'ice_on_new{}'.format(c)] = df.loc[:,'ice_on_new{}'.format(c)].astype(str).replace({'-999.0':'-999'})
        df.loc[:,'ice_off_new{}'.format(c)] = df.loc[:,'ice_off_new{}'.format(c)].astype(str).replace({'-999.0':'-999'})
    #dfcopy = df.copy()

    dropcolumns = ['Contributor','source','FileName','Updated Year']

    indiceon = (~df.ice_on_new_1.astype(str).isin(['-999','nan']) & 
                    df[['ice_on_new_{}'.format(ii) for ii in range(2,7)]+
                           ['ice_off_new_{}'.format(ii) for ii in range(1,7)]].astype(str).isin(['-999','nan']).all(axis=1) )
    indiceoff = (~df.ice_off_new_1.astype(str).isin(['-999','nan']) & 
                    df[['ice_off_new_{}'.format(ii) for ii in range(2,7)]+
                           ['ice_on_new_{}'.format(ii) for ii in range(1,7)]].astype(str).isin(['-999','nan']).all(axis=1) )

    dficeon = df[indiceon].reset_index()
    dficeoff = df[indiceoff].reset_index()
    dficeonoff = dficeon[[c for c in dficeon.columns if c!='ice_off_new_1']].merge(dficeoff[['index','NEWstart_year','lakecode','ice_off_new_1']+dropcolumns],left_on=['NEWstart_year','lakecode'],
                           right_on=['NEWstart_year','lakecode'],
                           how='inner',
                           validate='many_to_many')

    for i,row in dficeonoff.iterrows():
        indx = row.index_x
        indy = row.index_y
        # modify Contributor, source, filename as needed
        for cc in dropcolumns:        
            if row['{}_x'.format(cc)] != row['{}_y'.format(cc)]:
                newcolumn = '{} and {}'.format(row['{}_x'.format(cc)],row['{}_y'.format(cc)])
                #dficeonoff.loc[i,'{}'.format(cc)] = '{} and {}'.format(row['{}_x'.format(cc)],row['{}_y'.format(cc)])
            else:
                newcolumn = row['{}_x'.format(cc)]
            dficeonoff.loc[i,cc] = newcolumn
        
    dficeonoff = dficeonoff.drop(['{}_x'.format(cc) for cc in dropcolumns]+['{}_y'.format(cc) for cc in dropcolumns],axis=1)
    dficeonoff[['index_x','index_y','lakecode','NEWstart_year','ice_on_new_1','ice_off_new_1']+dropcolumns]

    for cc in dropcolumns+['ice_off_new_1','ice_on_new_1']:
        df.loc[dficeonoff.index_x,cc] = dficeonoff[cc].values
        df.loc[dficeonoff.index_y,cc] = dficeonoff[cc].values
    
    df.loc[:, 'nIceEvents'] = df[['ice_on_new_{}'.format(ii) for ii in range(1,7)]+
       ['ice_off_new_{}'.format(ii) for ii in range(1,7)]].fillna('-999').astype(str).replace({'-999':np.nan,'nan':np.nan}).count(axis=1).values
    df[['ice_on_new_{}'.format(ii) for ii in range(1,7)]+
           ['ice_off_new_{}'.format(ii) for ii in range(1,7)]] = df[['ice_on_new_{}'.format(ii) for ii in range(1,7)]+
           ['ice_off_new_{}'.format(ii) for ii in range(1,7)]].fillna('-999').astype(str)

    # Fill in frozeYN column if there is information
    df.loc[df.NEWfrozeYN.isnull() & 
                 ((df.loc[:,'ice_on_new_1':'ice_off_new_6']!='-999').any(axis=1) | 
                  (~df.loc[:,'NEWduration'].isnull() & (df.loc[:,'NEWduration']>0))),'NEWfrozeYN'] = 'Y'

    # Sort values so most recent Updated Year is at top. 
    # Drop duplicates based on all Ice On and Ice Off and FrozeYN columns
    df = df.sort_values(['lakecode','NEWstart_year','nIceEvents','Updated Year'],ascending=False).drop_duplicates(
        ['lakecode','NEWstart_year','NEWfrozeYN']+['ice_on_new_{}'.format(ii) for ii in range(1,7)]+
           ['ice_off_new_{}'.format(ii) for ii in range(1,7)]).copy()

    # Run through each duplicate year/lake and select the data to keep based on:
    #   - most recent Updated Year and max number of recorded ice events
    #  - bunch of rules for selecting one set of data over another (could try to assign codes 
    #        to contributors and sort as ordered categories)
    foo = 0
    droprows = []
    for name,group in df.groupby(['lakecode','NEWstart_year']):
        if len(group) > 1:
            # select rows with maximum nummber of nIceEvents and most recent data
            ind = ((group.nIceEvents == group['nIceEvents'].values[0]) & 
                  (group['Updated Year']==group['Updated Year'].values[0]))
            # If record shows both N and Y in the same year, then go with most recent observation
            if len(group.NEWfrozeYN.unique())!= 1:
                ind = (group['Updated Year']==group['Updated Year'].max())
            
            if ind.sum()==0:
                print ('BIG PROBLEM')
                break
            """
            if 35968 in group.index.tolist():
            
                if name[0] == 'xKB1881':
                display(group.dropna(how='all',axis=1))
                display(group[ind].dropna(how='all',axis=1))
                display(group[~ind].dropna(how='all',axis=1))
                input('continue?')
            else:
                continue"""
        
            if ((~ind).sum()>0):
                droprows.extend(group[~ind].index)
            
            if (ind.sum() > 1):
                # have to break the tie somehow
                ice1 = len(group.loc[ind,'ice_on_new_1'].unique())
                ice2 = len(group.loc[ind,'ice_off_new_1'].unique())
                if ind.sum()>2:
                    display(group.loc[ind,:].dropna(how='all',axis=1))
                    input('continue?')
                if (ice1!=1) | (ice2!=1):
                    clear_output(wait=True)
                    # Choose LTER over LIAG
                    if group.loc[ind,'Contributor'].isin(['LIAG','LTER']).all():
                        droprows.extend(group.loc[ind & (group[ind].Contributor=='LIAG'),:].index)
                    elif group.loc[ind,'Contributor'].isin(['Julia Daly']).all():
                        droprows.extend(group.loc[ind & (~group[ind].FileName.str.contains('Maine_lakes_long')),:].index)
                    elif group.loc[ind,'Contributor'].isin(['Julia Daly','Glenn Hodgkins']).all():
                        droprows.extend(group.loc[ind & (group[ind].Contributor=='Glenn Hodgkins'),:].index)
                    elif (group.loc[ind,'Contributor'].isin(['Ken Blumenfeld:Pete Boulay']).any() & 
                           group.loc[ind,'Contributor'].isin(['LIAG']).any() ):
                        # KEEP LIAG
                        droprows.extend(group.loc[ind & (group[ind].Contributor=='Ken Blumenfeld:Pete Boulay'),:].index)
                    elif (group.loc[ind,'Contributor'].str.contains('Ken Blumenfeld:Pete Boulay').all()):
                        checksource = df[df.lakecode==name[0]].source.value_counts().index[0]
                    
                        addindex = group.loc[ind & (group[ind].source!=checksource),:].index
                        droprows.extend(addindex)
                    elif (group.loc[ind,'Contributor'].isin(['LIAG']).any() & group.loc[ind,'Contributor'].isin(['Nickolay Grannin','Nickolay Granin']).any()):
                        # DROP LIAG
                        droprows.extend(group.loc[ind & (group[ind].Contributor=='LIAG'),:].index)
                    elif (group.loc[ind,'Contributor'].isin(['LIAG']).any() & group.loc[ind,'Contributor'].isin(['Dietmar Straile']).any()):
                        # KEEP LIAG
                        droprows.extend(group.loc[ind & (group[ind].Contributor=='Dietmar Straile'),:].index)
                    else:
                        #print(droprows,addindex,checksource)
                        print(name, droprows[-2:])
                        display(group[ind].replace({'-999':np.nan}).dropna(how='all',axis=1))
                        input('continue?')
                    #print(foo)
                    foo = foo+1
                else:
                    print(ice1,ice2)
                    # values are identical so it doesn't matter which row gets removed, but remove LTER over LIAG
                    # Little Rock lake (LR)
                    extra_index = group.loc[ind & (group[ind].Contributor=='LTER'),:].index
                    print('REMOVE EXTRA INDEX : ',extra_index)
                    droprows.extend(extra_index)
                    display(group.loc[ind,:])
                    print('BLEOM.CRASH')
                    #break
    df = df.drop(droprows)
    
    return df
        
    
def select_one_row_per_year(df, config):

    # if multiple freeze thaw events in one year for a given lake,
    #    needs to get merged into one row
    df = merge_rows(df)
    df = remove_lakecode_startyear_duplicates(df)
    
    # preferred data replacement
    df.loc[(df.lakecode=='ARAI1') & (df.NEWstart_year==1952),'ice_on_new_1'] = '1953-01-05'
    df.loc[(df.lakecode=='ARAI1') & (df.NEWstart_year==1976),'ice_on_new_1'] = '1976-12-30'
    indsebago = (df.NEWlake_english=='Sebago Lake *(see notes)') & (df.NEWstart_year.isin([2009,2011,2012,2015]))
    df.loc[indsebago, 'NEWfrozeYN'] = 'N'
    df.loc[indsebago, 'ice_on_new_1'] = '0'
    df.loc[indsebago, 'ice_off_new_1'] = '0'
    df.loc[indsebago, 'NEWfrozeYN column'] = 'adjusted to reflect Notes'

    return df
    
def reindex_by_date(df):
    dates = range(int(df.NEWstart_year.min()), int(df.NEWstart_year.max())+1)
    result = df.set_index('NEWstart_year').reindex(dates)
    c =['lakecode','NEWlake','NEWlatitude','NEWlongitude','NEWstate','NEWlake_english','NEWcity']
    result[c] = result[c].ffill()
    return result.reset_index()

def complete_time_series(df):


    finaldf = df.groupby('lakecode').apply(reindex_by_date).reset_index(0,drop=True)

    df = finaldf.replace({'nan':np.nan}).fillna(value={c:'-999' for c in ['ice_on_new_1','ice_off_new_1','ice_on_new_2','ice_off_new_2',
                                                   'ice_on_new_3','ice_off_new_3','ice_on_new_4','ice_off_new_4',
                                                   'ice_on_new_5','ice_off_new_5','ice_on_new_6','ice_off_new_6',
                                                  'NEWfrozeYN']})


    return df.reset_index(drop=True)
    
def add_doy_and_duration(df, duration_inclusive_day = 0):
    # duration_inclusive_day adds +1 day for those few cases where the lake froze and thawed on the same day
    # FOUR CASES:
    #   - toronto_harbor RAA5 1919-02-17 LIAG (Assel)
    #   - hallwilersee HJHF04 1922-02-08 Hendricks Franssen
    #   - ankarvattnet xKB0003 2017-12-04 Weyhenmeyer
    #   - balaton xTAK01 1910-01-09 Takacs
    # This is adjusted below (see ***)
    
    ind_nofreezeyears = df.loc[:,'NEWfrozeYN']=='N'

    for dd in ['_1','_2','_3','_4','_5','_6']:
        df['ice_on{}_doy'.format(dd)] = np.nan
        ind = ~ind_nofreezeyears & ~df['ice_on_new{}'.format(dd)].astype(str).isin(['-999'])
        #apply(lambda x: False if (x in ['-999','-999.0','nan']) else True)
        df.loc[ind,'ice_on{}_doy'.format(dd)] = df[ind].apply(lambda row: 
                         (pd.Period(year=int(row['ice_on_new{}'.format(dd)].split('-')[0]),
                                   month=int(row['ice_on_new{}'.format(dd)].split('-')[1]),
                                   day=int(row['ice_on_new{}'.format(dd)].split('-')[2]),freq='D') - 
                         pd.Period(year=int(row.NEWstart_year), 
                                   month=12, 
                                   day=31,freq='D')).n, axis=1)
        df.loc[ind, 'NEWfrozeYN{}'.format(dd)] = 'Y'
    #ind1 = ~ind_noiceoffyears & ~ind_nofreezeyears

    for dd in ['_1','_2','_3','_4','_5','_6']:
        df['ice_off{}_doy'.format(dd)] = np.nan
        ind = ~ind_nofreezeyears & ~df['ice_off_new{}'.format(dd)].astype(str).isin(['-999'])
        #apply(lambda x: True if (x in ['-999','-999.0','nan']) else False)
        df.loc[ind,'ice_off{}_doy'.format(dd)] = df[ind].apply(lambda row: 
                         (pd.Period(year=int(row['ice_off_new{}'.format(dd)].split('-')[0]),
                                   month=int(row['ice_off_new{}'.format(dd)].split('-')[1]),
                                   day=int(row['ice_off_new{}'.format(dd)].split('-')[2]),freq='D') - 
                         pd.Period(year=int(row.NEWstart_year), 
                                   month=12, 
                                   day=31,freq='D')).n, axis=1)
        df.loc[ind, 'NEWfrozeYN{}'.format(dd)] = 'Y'


    # Determine full season duration & max duration
    df['season_duration'] = -999
    #finaldf['max_duration'] = -999

    ind_duration = (~df[['ice_off_1_doy','ice_off_2_doy','ice_off_3_doy','ice_off_4_doy','ice_off_5_doy','ice_off_6_doy']].max(axis=1).isnull() &
          ~df[['ice_on_1_doy','ice_on_2_doy','ice_on_3_doy','ice_on_4_doy','ice_on_5_doy','ice_on_6_doy']].min(axis=1).isnull())

    df.loc[ind_duration, 'season_duration'] = (df.loc[ind_duration, ['ice_off_1_doy','ice_off_2_doy','ice_off_3_doy','ice_off_4_doy','ice_off_5_doy','ice_off_6_doy']].max(axis=1) -
          df.loc[ind_duration, ['ice_on_1_doy','ice_on_2_doy','ice_on_3_doy','ice_on_4_doy','ice_on_5_doy','ice_on_6_doy']].min(axis=1)) + duration_inclusive_day

    # Values for no-freeze years
    df.loc[ind_nofreezeyears,'season_duration'] = 0
    df.loc[ind_nofreezeyears,'ice_on_1_doy':'ice_off_6_doy'] = 998
    #finaldf.loc[ind_nofreezeyears,'ice_off_1_doy'] = 998
    for i in range(1,7):
        df['duration_{}'.format(i)] = np.nan
        ind_dur = (~df['ice_on_{}_doy'.format(i)].isnull() & 
                   ~df['ice_off_{}_doy'.format(i)].isnull() & 
                   ~df['ice_on_{}_doy'.format(i)].isin([998,-999]) & 
                   ~df['ice_off_{}_doy'.format(i)].isin([998,-999]))
        df.loc[ind_dur, 'duration_{}'.format(i)] = df.loc[ind_dur,'ice_off_{}_doy'.format(i)] - df.loc[ind_dur,'ice_on_{}_doy'.format(i)] + duration_inclusive_day
    # some rows where lake froze and thawed on the same day, so the above equation would yield 0 duration. 
    # modify these to be 1 day. (***)
        ind_zero = df['duration_{}'.format(i)]==0
        df.loc[ind_zero,'duration_{}'.format(i)] = 1    
        df.loc[ind_nofreezeyears,'duration_{}'.format(i)] = np.nan

    df['max_duration'] = df.loc[:,'duration_1':'duration_6'].max(axis=1)
    df['total_duration'] = df.loc[:,'duration_1':'duration_6'].sum(min_count=1, axis=1)
    # correct season duration too (***)
    ind = (df['total_duration'] > df['season_duration']) & (df.season_duration==0)
    if ind.sum()>0:
        print(df.loc[ind,:])
    df.loc[ind,'season_duration']=df.loc[ind,'total_duration']
    
    ind_missing =( ((df.NEWfrozeYN_1 =='Y') & df.duration_1.isnull()) | 
                    ((df.NEWfrozeYN_2 =='Y') & df.duration_2.isnull()) | 
                    ((df.NEWfrozeYN_3 =='Y') & df.duration_3.isnull()) | 
                    ((df.NEWfrozeYN_4 =='Y') & df.duration_4.isnull()) | 
                    ((df.NEWfrozeYN_5 =='Y') & df.duration_5.isnull()) | 
                    ((df.NEWfrozeYN_6 =='Y') & df.duration_6.isnull()) )
    
    df.loc[ind_missing,'total_duration'] = np.nan
    #df.loc[ind_missing,'season_duration'] = np.nan
    
    df.loc[ind_nofreezeyears,'max_duration'] = 0
    df.loc[ind_nofreezeyears,'duration_1'] = 0
    df.loc[ind_nofreezeyears,'total_duration'] = 0
    df.loc[ind_nofreezeyears,'NEWfrozeYN_1'] = 'N'
    #finaldf.loc[ind_noinfoyears,'ice_on_doy'] = -999
    #finaldf.loc[ind_noinfoyears,'ice_off_doy'] = -999
    return df


def fix_serwy(df):
    dfcopy = df.copy()
    ind1 = (dfcopy.lake=='serwy') & (dfcopy.ice_off_1_doy==(dfcopy.ice_on_2_doy-1)) & (dfcopy.ice_on_new_1=='-999') 
    dfcopy.loc[ind1,'ice_off_new_1'] = '-999'
    dfcopy.loc[ind1,'ice_off_1_doy'] = np.nan
    #display(dfsub4[ind1])
    ind1 = (dfcopy.lake=='serwy') & (dfcopy.ice_on_2_doy==(dfcopy.ice_off_1_doy+1)) & (dfcopy.ice_off_new_2 =='-999') 
    dfcopy.loc[ind1,'ice_on_new_2'] = '-999'
    dfcopy.loc[ind1,'ice_on_2_doy'] = np.nan
    return dfcopy

def get_final_columns(df):

    # clean up -999, 998 and '0' dates
    for c in df.columns:
        if ('ice_on' in c) | (c=='Source') | ('ice_off' in c) | ('frozeYN' in c) | ('duration' in c):
            for jj in ['-999.0','-999','998','998.0','-999.','998.','nan']:
                df.loc[:,c] = df.loc[:,c].astype(str).replace(jj,np.nan)
            if ('doy' not in c) & ('duration' not in c):
                df.loc[:,c] = df.loc[:,c].astype(str).replace('0',np.nan).replace('nan',np.nan).replace('0.',np.nan).replace('0.0',np.nan)
    
    
    
    newdict = {'NEWduration':'orig_duration','NEWduration column':'orig_duration_column',
               'NEWstart_year':'start_year','NEWfrozeYN':'froze', 
               'NEWfrozeYN_1':'froze_1',
               'NEWfrozeYN_2':'froze_2',
               'NEWfrozeYN_3':'froze_3',
               'NEWfrozeYN_4':'froze_4',
               'NEWfrozeYN_5':'froze_5',
               'NEWfrozeYN_6':'froze_6',
               'NEWlake_consistent':'lake',
               'NEWlake_alternates':'other_lakenames',
               'NEWlatitude_consistent':'Latitude',
               'NEWlongitude_consistent':'Longitude'}

    for i in range(1,7):
        newdict['ice_on_new_{}'.format(i)] = 'ice_on_{}'.format(i)
        newdict['ice_off_new_{}'.format(i)] = 'ice_off_{}'.format(i)

    final_columns = ['lakecode','lake',
      'start_year','froze']+['froze_{}'.format(i) for i in range(1,7)]+list(
        np.array(['ice_on_{}'.format(i) for i in range(1,7)]+['ice_off_{}'.format(i) for i in range(1,7)]).reshape(2,6).T.flatten())+list(
        np.array(['ice_on_{}_doy'.format(i) for i in range(1,7)]+['ice_off_{}_doy'.format(i) for i in range(1,7)]).reshape(2,6).T.flatten())+[                        
      'orig_duration','orig_duration_column','season_duration','max_duration','total_duration','Source','Contributor','Latitude','Longitude','other_lakenames','FileName']
    
    df = df.drop(['lake','Latitude','Longitude','froze','start_year'],axis=1).rename(
                    newdict,axis=1)[final_columns]
    df = df.rename({i:i.lower() for i in df.columns},axis=1)#.drop(['start_year.1'],axis=1)

    # add 'ice_on' and 'ice_off' as first freeze event and last thaw event of season
    df.loc[:,'ice_on'] = df.loc[:,'ice_on_1']
    df.loc[:,'ice_on_doy'] = df.loc[:,'ice_on_1_doy']

    df.loc[:,'ice_off'] = df.loc[:,'ice_off_1']
    df.loc[:,'ice_off_doy'] = df.loc[:,'ice_off_1_doy']

    # ice off is last ice date for lake 
    for i in range(1,7):
        ind = df['froze_{}'.format(i)]=='Y'
        df.loc[ind,'ice_off'] = df.loc[ind,'ice_off_{}'.format(i)]
        df.loc[ind,'ice_off_doy'] = df.loc[ind,'ice_off_{}_doy'.format(i)]
    #print(i,ind.sum())

                    
    return df
    
def latin_lakename(lakename):
    result = lakename.lower()
    replace_dict = {' ':'_',
                    ',':'_',
                    #'ä':'a',
                    #'Ä':'A',
                    #'Å':'A',
        u'\xc5':'A',
        u'\xc4':'A',
        u'\xd6':'O',
        u'\xe4':'a',
        u'\xf6':'o',
        u'\xc3\x84':'A',
        u'\xc3\x85':'A',
        u'\xc3\xa4':'a',
        u'\xc3\x96':'O',
        u'\xc3\xb6':'o',
    }
                    
    for key,value in replace_dict.items():
        result = result.replace(key,value)
    return result

def cleanup_minnesota(df):
    """ This is very inefficient. There is a much better way to do this.
        For ice on rows, keep MNDNR-LAKESDB, then MNPCA, then MNDNR-SCO in that order
        For ice off rows, keep MNDNR-SCO, then MNPCA, then MNDNR-LAKESDB
    """

    dfcopy = df.copy()
    indmissingsource = (dfcopy.source.isnull() | (dfcopy.source=='-999')) & ((dfcopy.Source!='-999') & ~dfcopy.Source.isnull())
    
    dfcopy.loc[indmissingsource,'source'] = dfcopy.loc[indmissingsource,'Source']
    
    indMN = dfcopy.lakecode.isin(dfcopy[dfcopy.NEWlake_english.str.contains('\(MN')].lakecode.unique())
    # remove duplicate rows, very inefficiently
    rmrows = []
    for name,group in dfcopy[indMN].groupby(['NEWstart_year','lakecode','FileName']):
        ind_on  = group.ice_on_new!='-999'
        ind_off = group.ice_off_new!='-999'
        rmrowsnew = []
        if len(group[ind_on].source.unique())>1:
            if 'MNDNR-LAKESDB' in group[ind_on].source.astype(str).str.strip().unique():
                rmrowsnew = group[ind_on & (group.source.astype(str).str.strip()!='MNDNR-LAKESDB')].index
            elif 'MNPCA' in group[ind_on].source.astype(str).str.strip().unique():
                rmrowsnew = group[ind_on & (group.source.astype(str).str.strip()!='MNPCA')].index
            elif 'MNDNR-SCO' in group[ind_on].source.astype(str).str.strip().unique():
                rmrowsnew = group[ind_on & (group.source.astype(str).str.strip()!='MNDNR-SCO')].index
            else:
                print('ICEON')
                display(group.dropna(how='all',axis=1))
                input('continue?')
            rmrows.extend(rmrowsnew)
            
        if len(group[ind_on].drop(rmrowsnew).drop_duplicates('ice_on_new')) > 1:
            ice_on_new = group[ind_on].drop(rmrowsnew).drop_duplicates('ice_on_new').sort_values('ice_on_new').ice_on_new.values
            if np.abs((pd.to_datetime(ice_on_new[0]) - pd.to_datetime(ice_on_new[1])).days) < 2:
                groupfoo = group[ind_on].drop(rmrowsnew)#.drop_duplicates('ice_on_new')
                rmrowsnew2 = groupfoo[groupfoo.ice_on_new != ice_on_new[0]].index
                rmrows.extend(rmrowsnew2)
                if len(groupfoo.drop(rmrowsnew2).drop_duplicates('ice_on_new'))>1:
                    display(group[ind_on].drop(rmrowsnew).drop(rmrowsnew2))
                    input('continue')
        
        rmrowsnew = []

        if len(group[ind_off].source.unique())>1:
        
            if 'MNDNR-SCO' in group[ind_off].source.astype(str).str.strip().unique():
                rmrowsnew = group[ind_off & (group.source.astype(str).str.strip()!='MNDNR-SCO')].index
            elif 'MNPCA' in group[ind_off].source.astype(str).str.strip().unique():
                rmrowsnew = group[ind_off & (group.source.astype(str).str.strip()!='MNPCA')].index
            elif 'MNDNR-LAKESDB' in group[ind_off].source.astype(str).str.strip().unique():
                rmrowsnew = group[ind_off & (group.source.astype(str).str.strip()!='MNDNR-LAKESDB')].index
            else:
                print('ICEOFF')
                display(group.dropna(how='all',axis=1))
                input('continue?')
            rmrows.extend(rmrowsnew)
        if len(group[ind_off].drop(rmrowsnew).drop_duplicates('ice_off_new')) > 1:
            ice_off_new = group[ind_off].drop(rmrowsnew).drop_duplicates('ice_off_new').sort_values('ice_off_new').ice_off_new.values
            if np.abs((pd.to_datetime(ice_off_new[0]) - pd.to_datetime(ice_off_new[1])).days) < 2:
                groupfoo = group[ind_off].drop(rmrowsnew)#.drop_duplicates('ice_on_new')
                rmrowsnew2 = groupfoo[groupfoo.ice_off_new != ice_off_new[0]].index
                rmrows.extend(rmrowsnew2)
                if len(groupfoo.drop(rmrowsnew2).drop_duplicates('ice_off_new'))>1:
                    display(group[ind_off].drop(rmrowsnew).drop(rmrowsnew2))
                    input('continue')
            #if len(group[ind_off].drop(rmrowsnew).drop_duplicates('ice_off_new')) > 1:
            #    display(group[ind_off].drop(rmrowsnew))
            #    input('continue')
    
    dfcopy = dfcopy.drop(rmrows)
    
    return dfcopy

def shorten_lake(lake):
    # remove word lake unless Lake of Bays or Lake of the woodsother?
    # also remove parentheses

    no_remove_lake = ['lake of','bay lake','lake of the woods','lakes']#,'lake of the isles']
    no_remove_parentheses = ['south bay ( huron)']
    result = lake.lower().strip()
    if not np.any([i in result for i in no_remove_lake]):
        result = result.replace('lake','')
    if not np.any([i in result for i in no_remove_parentheses]):
        regexp = "\((.*?)\)"
        result = re.sub(regexp,'',result)
    result = ' '.join([i for i in result.split()])
    return result.strip()

def clean_lakenames(df):
    dfcopy = df.copy()
    # remove word lake unless Lake of Bays or other?
    # also remove parentheses

    # select the shortest lake name
    result = dfcopy.apply(lambda x: latin_lakename([shorten_lake(i) for i in x if 
                                          len(shorten_lake(i)) == min([len(shorten_lake(j)) 
                                          for j in x])][0]))
    return result
    
def make_lakenames_consistent(df, lakecolumn='NEWlake'):
    dfcopy = df.copy()
    lakealternates = dfcopy.groupby('lakecode')[lakecolumn].unique()
    lakealternates_list = lakealternates.apply(lambda x: ';'.join([i.strip() for i in x])).rename('{}_alternates'.format(lakecolumn))
    lakeconsistent = clean_lakenames(lakealternates).rename('{}_consistent'.format(lakecolumn))
    dfcopy = dfcopy.merge(lakealternates_list, left_on='lakecode',right_index=True, how='left', validate='many_to_one')
    dfcopy = dfcopy.merge(lakeconsistent, left_on='lakecode',right_index=True, how='left', validate='many_to_one')
    
    return dfcopy

def clean_latlon(df, latcolumn='NEWlatitude',loncolumn='NEWlongitude'):
    dfcopy = df.copy()
    for name,group in dfcopy.groupby('lakecode'):
        if len(group[[latcolumn,loncolumn]].drop_duplicates())>1:
            dfcopy.loc[dfcopy.lakecode==name,'latlon_alternates'] = ';'.join(group.drop_duplicates([latcolumn,loncolumn])[[latcolumn,loncolumn]].astype(str).apply(lambda x: '({},{})'.format(x[latcolumn], x[loncolumn]),axis=1).values)
            # keep most precise lat lon measure (only first occurrence)
            # tried to correct for Suwa/GTB corrections by specifying more precision, when corrected above
            # Should pick out corrected Lake Suwa value (36.040 over 36.15)
            # But GTB also should be 44.770, not 44.75
            keeprow = group.drop_duplicates([latcolumn,loncolumn]).apply(lambda x: len(str(x[latcolumn])+str(x[loncolumn])),axis=1).idxmax()
            #print(keeprow)
            latitude= group.loc[keeprow,latcolumn]
            longitude = group.loc[keeprow,loncolumn]
            #print(latitude,longitude)
            dfcopy.loc[dfcopy.lakecode==name,'{}_consistent'.format(latcolumn)] = latitude
            dfcopy.loc[dfcopy.lakecode==name,'{}_consistent'.format(loncolumn)] = longitude
        else:
            dfcopy.loc[dfcopy.lakecode==name,'{}_consistent'.format(latcolumn)] = group[latcolumn].values[0]
            dfcopy.loc[dfcopy.lakecode==name,'{}_consistent'.format(loncolumn)] = group[loncolumn].values[0]
    return dfcopy

def add_liag_contributors(df,config):
    liagfilename = config.get('FILES','liag_contributors')
    dfliag = pd.read_excel(liagfilename)
    dfliag.lakecode = dfliag.lakecode.str.strip()
    # merge entire database
    dfoo = df.merge(dfliag[['lakecode','contributor']].rename({'contributor':'liag_contributor'},axis=1),left_on='lakecode',right_on='lakecode',how='left',validate='many_to_one')
    # copy only relevant information ('contributor') to final database
    dfcopy = df.copy()
    dfcopy.loc[dfoo.Contributor.astype(str).str.contains('LIAG'),'Contributor'] = dfoo.loc[dfoo.Contributor.astype(str).str.contains('LIAG'),
            ['Contributor','liag_contributor']].apply(
            lambda row: (row.Contributor).replace('LIAG','LIAG ({})'.format(row.liag_contributor.strip())),
            axis=1)
#    dfoo.loc[dfoo.Contributor.str.contains('LIAG'),'liag_contributor'].apply(lambda x: 'LIAG ({})'.format(x.strip()))
    return dfcopy

    
if __name__ == "__main__":
    verbose = True
    
    # Set up config file where specific definitions. instructions,
    #      rules are stored.
    config = configparser.ConfigParser()
    config.read('../ini/config_lakeiceTS.ini')
    
    # Set up log file 
    logfile = '../logs/lakeiceTS_{}.log'.format(origtime)
    f = open(logfile, 'w')
    
    """ STEP ONE. Create large dataframe containing all data.
        Read in all files of type csv, xls, xlsx, txt, PDF 
    """
    # Get list of all files, sorted by file type
    rootdir = config.get('INPUT','rootdir')
    exclude_files = config.get('INPUT','exclude_files').split('\n')
    exclude_dirs = config.get('INPUT','exclude_dirs').split('\n')
    fileinfo = eval(config.get('FILE_INFO','files'))
    julian_fileinfo = eval(config.get('FILE_INFO','julian_files'))
    # get_all_filenames returns a (key, value) dictionary where
    #   the keys are file type ('xls', 'doc', 'csv') and value is
    #   the list of all files of that type in the directory structure
    filenames = get_all_filenames(rootdir,exclude_files=exclude_files,exclude_dirs=exclude_dirs)
    # print(len(filenames))

    if verbose:
        print('Reading in all files in {}'.format(rootdir))
    
    df = read_all_files(filenames, fileinfo, logfile=f,verbose=False)
    
    if verbose:
        print('Rows read in: {}'.format(df.shape[0]))
    
    # Now need to fix special cases
    if verbose:
        print('\rFixing special cases...')
    df = fix_special_cases(df)
    if verbose:
        print('\rConverting Julian day to date...')
    df = julian_day_to_date(df, julian_fileinfo)
    if verbose:
        print('\rCreating common column headers...')
    df = create_common_column_headers(df, config) #... and fixes lake names
    if verbose:
        print('\rFix typos...')
    df = fix_typos(df, config)
    if verbose:
        print('\rDetermining ice-free years...')
    df = determine_icefree_years(df, logfile=f)
    
    # For postcard data, multiple ice-on and ice-off sometimes show up in the same cell
    #  Split these into separate lines
    #df = split_iceon_iceoff(df)
    
    if verbose:
        print('\rReformatting iceon and iceoff dates...')
    df = reformat_iceon_iceoff(df)
    # Fix lake names (Merge with MN lake database and add real LTER lake names)
    #df = update_lake_names(df, config)
    
    # Assign lakecodes to lakes
    
    """ TO DO: Modify so new lakecodes get created when none exists already  """
    """ Alternatively, add to .ini file lakecodes you want to assign to lake """
    if verbose:
        print('\rAssigning lakecodes to each lake/location/contributor combination...')
    df = assign_lakecodes(df, config)
    # clean up lakecode
    df.lakecode = df.lakecode.str.strip()
    
    ###  Korhonen missing lakecodes and "Sebago NOTES" missing lake codes.
    ### That's OK.
    #if df.lakecode.isnull().sum() > 0:
    #    print('MISSING LAKECODES')

    # Select one row per lake (lakecode) per year
    # Ensure start years are all presented as integers
    if verbose:
        print('\rSelecting one row per year per lake...')
    df['NEWstart_year'] = df['NEWstart_year'].astype(float).astype(int)
    df = cleanup_minnesota(df)
    df = select_one_row_per_year(df, config)

    # Complete time series by filling in empty missing rows
    if verbose:
        print('\rCompleting time series...')
    df = complete_time_series(df)
    
    # calculate day of year, complete season duration and max ice period
    if verbose:
        print('\rAdding day of year and extra duration columns...')
    df = add_doy_and_duration(df)

    df = make_lakenames_consistent(df, lakecolumn='NEWlake')
    df = clean_latlon(df, loncolumn='NEWlongitude', latcolumn='NEWlatitude')

    df = add_liag_contributors(df, config)

    # Quality checks
    #    - do all lakes have latitude, longitude?
    #    - do all lakes have a lakecode, lake name?
    #    - are all ice durations zero or positive?
    df = fix_serwy(df)

    df.to_csv('../all_timeseries_preliminary.csv',index=False)

    # extract only certain columns, and clean up 998 and -999 
    #   add add first freeze and last thaw as separate columns
    df = get_final_columns(df)
    df.to_csv('../all_lakes_ts_reduced.csv', index=False)
    print(df.columns)
    
    
    f.close()
    

