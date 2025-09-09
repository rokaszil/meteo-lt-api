import pandas as pd
import requests
import datetime
import time 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from zoneinfo import ZoneInfo

# 1. Duomenu nuskaitymo klase

class meteo_data:

    def __init__(self, api_url):
        self.api_url = api_url
    
    def forecast(self, location):    # Prognoziu nuskaitymas. Pateikiamas vietos kodas
        response = requests.get(self.api_url + "/places/" + location + "/forecasts/long-term")
        fcst = pd.DataFrame(response.json().get('forecastTimestamps'))
        fcst['forecastTimeUtc'] = pd.to_datetime(fcst['forecastTimeUtc'])
        fcst['forecastTimeUtc'] = fcst['forecastTimeUtc'].dt.tz_localize('UTC').dt.tz_convert('Europe/Vilnius')
        fcst.set_index('forecastTimeUtc', inplace=True)
        return fcst
        
    def observations(self, station, date_from, date_until):    # Istoriniu matavimu nuskaitymas. Pateikiamas stoties kodas bei datos intervalas. date_from ir date_until formatas: YYYY-MM-DD
        max_date = datetime.datetime.strptime(date_until, '%Y-%m-%d').replace(tzinfo=ZoneInfo("Europe/Vilnius"))
        min_date = datetime.datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=ZoneInfo("Europe/Vilnius"))
        min_date_utc = min_date - datetime.timedelta(days=1)   # Kadangi API pateikia duomenis UTC laiko zonoje, reikia itraukti ir ankstesnes dienos matavimus, nes kai kurie ju papuola i nauja diena pagal faktine Lietuvos laiko juosta
        obs_list = []
        for i, d in enumerate(pd.date_range(start=min_date_utc, end=max_date), start=1):   # Meteo.lt API leidzia pasirinkti tik viena data uzklausai, todel reikalingas ciklas
                    response = requests.get(self.api_url + "/stations/" + station + "/observations/" + d.strftime('%Y-%m-%d'))
                    obs_list.extend(response.json().get('observations'))
                    if i%180 == 0:              # Meteo.lt API leidzia max 180 uzklausu per minute. Kadangi vienos uzklausos trukme apie 0.2 - 0.5s, atsiranda rizika virsyti apribojima. Todel iterpta pauze kas 180 uzklausu.
                          time.sleep(30)

        obs = pd.DataFrame(obs_list)
        obs['observationTimeUtc'] = pd.to_datetime(obs['observationTimeUtc'])
        obs['observationTimeUtc'] = obs['observationTimeUtc'].dt.tz_localize('UTC').dt.tz_convert('Europe/Vilnius')
        obs.set_index('observationTimeUtc', inplace=True)
        obs = obs[(obs.index.date >= min_date.date()) & (obs.index.date <= max_date.date())]  # palikti tik irasus papuolancius i reikiamas datas Lietuvos laiko zonoje 
        return obs


# 2a. Vidutinė metų temperatūra, oro drėgmė

observations = meteo_data("https://api.meteo.lt/v1").observations("kauno-ams", '2024-09-10', '2025-09-09')
print("Vidutinė metų temperatūra: ", round(observations['airTemperature'].mean(), 1)) # kadangi duomenys yra vienodais intervalais, galima skaičiuoti aritmetinį vidurkį
print("Vidutinė metų oro dregme: ", round(observations['relativeHumidity'].mean(), 1)) 
 
# 2b. Vidutinė metų dienos ir nakties temperatūra

day_temp =  observations[(observations.index.time >= datetime.time(8, 0, 0)) & (observations.index.time <= datetime.time(20, 0, 0))]
night_temp = observations[(observations.index.time < datetime.time(8, 0, 0)) | (observations.index.time > datetime.time(20, 0, 0))]
print("Vidutinė metų dienos temperatūra: ", round(day_temp['airTemperature'].mean(), 1))
print("Vidutinė metų nakties temperatūra: ", round(night_temp['airTemperature'].mean(), 1))

# 2c. Lietingu savaitgaliu skaiciavimas. Itraukiamos tik tos dienos, kuriose buvo su lietumi (bet ne sniegu) susije krituliai
rain_conditions = ['rain', 'rain-showers', 'light-rain-at-times', 'rain-at-times', 'light-rain', 'rain', 'heavy-rain', 'isolated-thunderstorms', 'thunderstorms']
rain = observations[observations['conditionCode'].isin(rain_conditions)]
date_list = pd.to_datetime(pd.Series(observations.index.date).drop_duplicates())
saturdays = date_list[date_list.dt.weekday == 5].count() #sestadieniu skaicius
sundays = date_list[date_list.dt.weekday == 6].count() # sekmadieniu skaicius
number_of_weekends = max(saturdays, sundays)        # kadangi tiek sestadienis, tiek ir sekmadienis yra savaitgalis, imame didesni skaiciu
print("Lietingų savaitgalių skaičius: ", number_of_weekends) 

# 3. Prognozes nuskaitymas ir sujungimas su istoriniais matavimais. Praeitos ir ateinancios savaites atvaizdavimas grafike

forecast = meteo_data("https://api.meteo.lt/v1").forecast("kaunas")
forecast.columns = observations.columns
all_data = pd.concat([observations, forecast[forecast.index.isin(observations.index) == False]]) # Istoriniu duomenu ir prognoziu sujungimas, paliekant prioriteta istoriniams duomenims

fig, ax = plt.subplots()
ax.set_ylabel('Oro temperatūra (°C)')
ax.set_xlabel('Data')
ax.xaxis.set_minor_locator(mdates.DayLocator())
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_minor_formatter(mdates.DateFormatter('%d'))
data_to_plot = all_data[(all_data.index.date >= datetime.date(2025, 9, 3)) & (all_data.index.date <= datetime.date(2025, 9, 16))]
data_to_plot['airTemperature'].plot(title="Oro temperatūra: matavimai ir prognozė")
ax.grid(True)
ax.tick_params(axis = 'x', which='major', pad=20, labelrotation=0)
# plt.show()

# 4. Duomenų interpoliacijos funkcija padidinus laiko indekso dazni

def interpolate (series):
    return series.resample('5min').interpolate()
    
print("Interpoliacijos pavyzdys - oro temperatūra: ", interpolate(data_to_plot['airTemperature']))


