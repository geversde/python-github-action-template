from bs4 import BeautifulSoup
import pytz


import time
import pandas as pd
import lxml
import requests
import json
from datetime import datetime, date, timedelta

t1 = time.time()
def get_pv_c(dew_c):
    c0 = 0.99999683
    c1 = -0.90826951 * 10**-2
    c2 = 0.78736169 * 10**-4
    c3 = -0.61117958 * 10**-6
    c4 = 0.43884187 * 10**-8
    c5 = -0.29883885 * 10**-10
    c6 = 0.21874425 * 10**-12
    c7 = -0.17892321 * 10**-14
    c8 = 0.11112018 * 10**-16
    c9 = -0.30994571 * 10**-19
    T = dew_c
    p = c0 + T * (c1 + T *(c2 + T *(c3 + T *(c4 + T *(c5 + T *(c6 + T *(c7 + T *(c8 + T *(c9) ) ) ) ) ) ) ))
    e = 6.1078
    Es = e/(p**8)
    return Es
def get_rho_metric(temp_c, ap_m, dew_c = 10):
    pv = get_pv_c(dew_c)
    p0 = ap_m
    pd = p0-pv
    rho = pd / (287.0531 * (temp_c + 273.15) ) + pv / (461.4964* (temp_c + 273.5) )
    return (rho*100)
mlb_stadiums = pd.read_csv("/Users/grahameversden/Downloads/mlb_stadiums - mlb_stadiums.csv-2.csv")

def get_time_per(t1, t2, target_time):
    t1dif = abs(t1 - target_time).total_seconds()
    t2dif = abs(t2 - target_time).total_seconds()
    t1perc = t1dif/(t1dif+t2dif)
    return (t1perc)

def get_values(df, i1, i2, perc):
    ap = float(df["Air Pressure"][i1]) * perc + float(df["Air Pressure"][i2]) *(1-perc)
    temp = float(df["Air Temp"][i1]) * perc + float(df["Air Temp"][i2]) *(1-perc)
    return (temp, ap)

def try2(team, gametime, stadium_df):
    #print(team)
    time.sleep(1)
    condition  = stadium_df["Abbreviation"] == team
    lnk = stadium_df.loc[condition, "Wind Finder Link"].iloc[0]
    response = requests.get(lnk)
    soup = BeautifulSoup(response.content, 'html.parser')
    hour = soup.find_all('span', class_='value')
    temperature = soup.find_all("span", class_ = "units-at")
    air_pressure = soup.find_all("span", class_ = "units-ap")
    hours = []
    for el in hour:
        if "h" in el.text:
            hours.append(el.text)
    temps = []
    for tp in temperature:
        temps.append(tp.text) #this is celcius
    pressures = []
    for ap in air_pressure: #this the other version, not imperial
        pressures.append(ap.text)
    #target_time = datetime.combine(date.today(), datetime.strptime(gametime, "%H:%M").time())
    target_time = gametime
    air_pressure = pd.DataFrame([hours, pressures, temps]).transpose()
    air_pressure.columns = ["Time", "Air Pressure","Air Temp"]
    air_pressure = air_pressure[:8]
    try:
        time_str = [tmhelper.replace("h", "") for tmhelper in air_pressure["Time"]]
        air_pressure["time_f"] = [datetime.combine(date.today(), datetime.strptime(timer, "%H").time()) for timer in time_str]
    except:
        air_pressure["time_f"] = [datetime.combine(date.today(), datetime.strptime(timer, "%H")) for timer in air_pressure["Time"]]
    
    correct_index = min(range(len(air_pressure["time_f"])), key=lambda i: abs(air_pressure["time_f"][i] - target_time))
    sorted_segments = sorted(air_pressure["time_f"], key=lambda x: abs(target_time - x)) #gets the two closest times to the start time of the game
    t1perc_early = get_time_per(sorted_segments[0], sorted_segments[1], target_time) #gets the percent of index1 we should use
    #print(t1perc_early)
    target2 = target_time + timedelta(hours = 2)
    sorted_segments_late = sorted(air_pressure["time_f"], key=lambda x: abs(target2 - x)) #gets the two closest times to 2 hours into game
    t1perc_late = get_time_per(sorted_segments_late[0], sorted_segments_late[1], target2) #
    #print(t1perc_late)
    index1early = air_pressure["time_f"].tolist().index(sorted_segments[0])
    index2early = air_pressure["time_f"].tolist().index(sorted_segments[1])
    index1late = air_pressure["time_f"].tolist().index(sorted_segments_late[0])
    index2late = air_pressure["time_f"].tolist().index(sorted_segments_late[1])
    early_values = get_values(air_pressure, index1early, index2early, t1perc_early)
    late_values = get_values(air_pressure, index1late, index2late, t1perc_late)

    rho = (get_rho_metric(early_values[0], early_values[1]), get_rho_metric(late_values[0], late_values[1]))
    #print(team)

    return(rho)

dt = datetime.today().strftime("%Y%m%d")
response = requests.get("https://www.espn.com/mlb/schedule/_/date/" + dt)
soup = BeautifulSoup(response.content, 'html.parser')
table = soup.find("table", class_ = "Table")
lst = pd.read_html(str(table))[0]
lst["cities"] = [string.lstrip('@').strip() for string in lst["MATCHUP.1"]]
mlb_info = pd.read_csv("/Users/grahameversden/Downloads/mlb_info.csv")

merged = pd.merge(lst, mlb_info, left_on = "cities", right_on = "City", how = "inner")
merged["time_f"] = [datetime.combine(date.today(), datetime.strptime(time_str, "%I:%M %p").time()) for time_str in merged["TIME"]]
orig_tz = pytz.timezone('US/Eastern')
local_time = []
for i in range(len(merged)):
    new_tz = merged["Time Zone"][i]
    local_time.append(orig_tz.localize(merged["time_f"][i], is_dst = None).astimezone(new_tz))
local2 = []
for tz in local_time:
    local2.append(tz.replace(tzinfo=None))
merged["local"] = local2
game_rhos = merged.apply(lambda row: try2(row["Abbreviation"], row["local"], mlb_info), axis = 1)
reshaped_data = [(x, y) for x, y in game_rhos]
rhos_split = pd.DataFrame(reshaped_data, columns=['early', 'late'])
merged["early_rho"] = rhos_split["early"]
merged["late_rho"] = rhos_split["late"]
final = merged[["MATCHUP", "MATCHUP.1", "early_rho", "late_rho"]]
t2 = time.time()

print(final)
print(t2-t1)
final.to_csv("/Users/grahameversden/Documents/Mlb_rhos/" + dt+ ".csv")