import threading
import json
import logging
import sched
import time
import requests
import pyttsx3
from flask import Flask, render_template
from flask import request

APP = Flask(__name__)
# Intialise global lists holding alarm information.
# These lists are printed on the main web page, allowing users to see their alarms.
ALARM_LIST = []
ALARM_ACTIVE = []
ALARM_EXPIRED_LIST = []
THREADS = []
# LOCATION for weather can be updated in a single LOCATION.
LOCATION = 'Exeter'
# Sched variable is initialised.
SCHEDULER = sched.scheduler(time.time, time.sleep)
# JSON file containing keys for API is opened and data is read and assigned
with open('config.json') as config_file:
    DATA = json.load(config_file)
WEATHER_KEY = DATA['weather_key']
NEWS_KEY = DATA['news_key']
# Logging file is created.
logging.basicConfig(filename='smart_alarm.log', level=logging.DEBUG)

def get_weather() -> str:
    """ Returns weather information as a string list from API """
    # API address is formed using multiple variables.
    api_address = 'http://api.openweathermap.org/data/2.5/weather?appid=' + WEATHER_KEY + '&q='
    url = api_address + LOCATION
    # Weather list is initialised.
    weather_update = []
    # API is used to populate variables with relevant information.
    json_data = requests.get(url).json()
    weather_description = json_data['weather'][0]['description']
    weather_description = 'Description: ' + weather_description
    weather_update.append(weather_description)
    # Temperature is put into °C format.
    temperature = round(json_data['main']['temp'] - 272.15, 2)
    temperature = 'Temperature: ' + str(temperature) + ' °C'
    weather_update.append(temperature)
    windspeed = json_data['wind']['speed']
    windspeed = 'Windspeed: ' + str(windspeed) + ' mph'
    weather_update.append(windspeed)
    # Full weather update is returned.
    return weather_update

def get_icon() -> str:
    """ Returns the web address which holds the specific icon to the weather. """
    # API address is formed using multiple variables.
    api_address = 'http://api.openweathermap.org/data/2.5/weather?appid=' + WEATHER_KEY + '&q='
    url = api_address + LOCATION
    json_data = requests.get(url).json()
    icon = json_data['weather'][0]['icon']
    # URL of icon for weather is returned.
    return icon

def get_news() -> str:
    """ Returns news information as a string list from API. """
    # News list is initialised.
    news_headlines = []
    # API address is formed using multiple variables.
    url = 'https://newsapi.org/v2/top-headlines?sources=bbc-news&apiKey=' + NEWS_KEY
    json_data = requests.get(url).json()
    counter = 0
    # Counter and while loop is used to loop through the top 3 news stories.
    while counter <= 4:
        # Title and description are retrieved.
        news_title = json_data['articles'][counter]['title']
        news_description = json_data['articles'][counter]['description']
        news = news_title + ': ' + news_description
        news_headlines.append(news)
        counter = counter + 1
    # Full list of headlines are returned
    return news_headlines

def get_sport_news() -> str:
    """ Returns sports news information as a string list from API. """
    # Sports news list is initialised
    sport_headlines = []
    # API address is formed using multiple variables.
    url = 'https://newsapi.org/v2/top-headlines?sources=bbc-sport&apiKey=' + NEWS_KEY
    json_data = requests.get(url).json()
    counter = 0
    # Counter and while loop is used to loop through the top 3 sports stories.
    while counter <= 2:
        # Title and description are retrieved.
        sport_title = json_data['articles'][counter]['title']
        sport_description = json_data['articles'][counter]['description']
        sport = sport_title + ': ' + sport_description
        sport_headlines.append(sport)
        counter = counter + 1
    # Full list of sports headlines are returned.
    return sport_headlines


def new_alarm(description: str, alarm: str, repeat=''):
    """
    Creates a new alarm using the arguments provided from user via the web interface.
    A thread is started and the alarm is run in that.
    """
    # Day and time of alarm is spliced from full date and time.
    day = alarm[0:10]
    alarm_time = alarm[11:16]
    # User friendly alarm description is generated.
    alarm_description = 'Alarm for ' + description + ' set at ' + alarm_time + ' on ' + day
    end_date = day + ' ' + alarm_time + ':00'
    # Current time and end time of alarm in seconds is calculated
    current_time = time.time()
    end_date_seconds = time.mktime(time.strptime(end_date, '%Y-%m-%d %H:%M:%S'))
    # Length of time the alarm is needed to be set for is calculated.
    time_difference = end_date_seconds - current_time
    # New thread created to hold new alarm.
    if repeat == 'true':
        # Repeating alarm will be set if user ticks box on main web page.
        SCHEDULER.event = SCHEDULER.enter(time_difference, 1, \
        alarm_expired_repeat, argument=(description,))
        # Active alarm is appended to the list of all active alarms, allowing it to be cancelled.
        ALARM_ACTIVE.append(SCHEDULER.event)
        # User is notified of alarm creation via speech.
        speech(alarm_description + ' every week.')
    else:
        SCHEDULER.event = SCHEDULER.enter(time_difference, 1, alarm_expired, \
        argument=(description, alarm_description))
        # Active alarm is appended to the list of all active alarms, allowing it to be cancelled.
        ALARM_ACTIVE.append(SCHEDULER.event)
        # User is notified of alarm creation via speech.
        speech(alarm_description)
    # Alarm creation is logged.
    logging.info(alarm_description)
    # Alarm begins
    SCHEDULER.run()

def alarm_expired(description: str, alarm_description: str):
    """
    Uses 2 string arguments to create silent and audio notifications for the user
    when an alarm expires.
    """
    # User is notified of alarm expiration via silent notification.
    ALARM_EXPIRED_LIST.append(alarm_description + ' has expired.')
    alarm_description = alarm_description + '.'
    # The position of the alarm in the list is found and the alarm is
    # removed from the list of active alarms.
    index_alarm = ALARM_LIST.index(alarm_description)
    ALARM_LIST.pop(index_alarm)
    # Expiration of alarm is logged.
    logging.info(alarm_description + ' has expired.')
    # User is notified of alarm expiration via loud notification.
    speech('Alarm for ' + description + 'has expired.')

def alarm_expired_repeat(description: str):
    """
    Uses string argument to provide expired alarm message to user aswell as creating a new alarm.
    """
    # Repeating alarm message is spoken to user.
    speech('Alarm for ' + description + ' has expired. Alarm set for the same time next week.')
    # A silent notification is also produced.
    ALARM_EXPIRED_LIST.append('Alarm for ' + description + \
    ' has expired. Alarm set for the same time next week.')
    # New thread is created which will hold the same alarm but for 1 week later.
    new_thread = threading.Thread(target=repeat_alarm, args=(description))
    # The new thread begins.
    new_thread.start()
    THREADS.append(new_thread)

def repeat_alarm(description: str):
    """
    Uses string argument to create a new alarm when the repeating alarm expires.
    This function will call itself after 1 week.
    """
    # Alarm is set for 604800 seconds (1 week).
    SCHEDULER.event = SCHEDULER.enter(604800, 1, alarm_expired_repeat, argument=(description,))
    ALARM_ACTIVE.append(SCHEDULER.event)
    SCHEDULER.run()


def cancel_alarm(description: str):
    """
    Uses a single string argument to notify user of cancelled alarm.
    """
    # Checks if description entered is in the list of alarms.
    if description in ALARM_LIST:
        # Position of alarm in list of alarms is found by searching for its description.
        index_alarm = ALARM_LIST.index(description)
        # If list is not empty, the alarm is removed from list of alarms.
        if len(ALARM_LIST) > 0:
            ALARM_LIST.pop(index_alarm)
        # The alarm in the same index in the active alarm list is then found and cancelled.
        alarm = ALARM_ACTIVE[index_alarm]
        SCHEDULER.cancel(alarm)
        # Cancellation is logged.
        logging.info(description + ' has been cancelled.')
        if len(ALARM_ACTIVE) > 0:
            # If list is not empty, the alarm is removed from list of active alarms.
            ALARM_ACTIVE.pop(index_alarm)
        # Cancelled alarm is added to user notification bar.
        ALARM_EXPIRED_LIST.append(description + ' has been cancelled.')
        # USer is notified of this cancellation.
        speech('Alarm for ' + description + ' has been cancelled.')
    else:
        # User notified of their error.
        speech('The alarm you have entered is not valid.')

def speech(speech: str):
    """ A string argument is provided and this is the read out via text to speech. """
    # Text to speech is used to notify user of any major change.
    engine = pyttsx3.init()
    engine.say(speech)
    engine.runAndWait()

def append_alarm(description: str, alarm: str, repeat: str):
    """ Uses 3 string arguments to append a new alarm to the current alarm list. """
    # Date and time of alarm are selected from longer alarm time string.
    day = alarm[0:10]
    alarm_time = alarm[11:16]
    # User friendly description is generated.
    alarm_description = 'Alarm for ' + description + ' set at ' + alarm_time + ' on ' + day
    if repeat == 'true':
        # if repeating alarm, the description is altered slightly.
        alarm_description = alarm_description + ' every week.'
    else:
        alarm_description = alarm_description + '.'
    # Description added to list of alarms.
    ALARM_LIST.append(alarm_description)

@APP.route('/')
@APP.route('/home')
def home():
    # All APIs are refreshed and kept updated every time the page reloads (every 30 seconds).
    weather_update = get_weather()
    news_headlines = get_news()
    sport_headlines = get_sport_news()
    icon = get_icon()
    # Data from URL is retrieved and stored into variables.
    alarm = request.args.get('alarm')
    description = request.args.get('description')
    repeat = request.args.get('repeat')
    alarm_cancel = request.args.get('cancel')
    notification_clear = request.args.get('clear')
    # If user clears notifications, the list of expired alarms is cleared.
    if notification_clear:
        ALARM_EXPIRED_LIST.clear()
        logging.info('Notifications cleared.')
    # if the user chooses to cancel an alarm, the cancel_alarm fucntion is called.
    if alarm_cancel:
        cancel_alarm(alarm_cancel)
    # will be called if user produced a time and description for the alarm.
    if alarm and description:
        # New alarm is added to alarm list.
        append_alarm(description, alarm, repeat)
        # New thread begins allowing a new alarm to be created and ran whilst
        # allowing main program to execute.
        new_thread = threading.Thread(target=new_alarm, args=(description, alarm, repeat))
        new_thread.start()
        # Thread is added to list of active THREADS.
        THREADS.append(new_thread)
    # HTML for the webpage is loaded and variableds are passed into flask.
    return render_template('webPage.html', weather_update=weather_update, \
    news_headlines=news_headlines, sport_headlines=sport_headlines, \
    alarm_list=ALARM_LIST, icon=icon, location=LOCATION, alarm_expired_list=ALARM_EXPIRED_LIST)

# Allows program to be executed.
if __name__ == '__main__':
    APP.run(debug=True)
