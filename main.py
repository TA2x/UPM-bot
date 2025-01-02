import discord
from discord.ext import commands
from termcolor import colored
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from colorama import Fore, Style, init
from datetime import datetime, timedelta
import requests
import pyfiglet

# Initialize Discord bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global session objects
session = requests.Session()
Digi_session = requests.Session()
login_response = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")

@bot.command()
async def login(ctx, student_id: str, password: str, digi_password: str):
    """Command to log in and establish sessions."""
    global login_response

    # SIS Login
    login_url = "https://sis.upm.edu.sa/psp/ps/?=&cmd=login&languageCd=ENG"
    payload = {"userid": student_id, "pwd": password}
    headers = {'User-agent': 'Mozilla/5.0'}
    response = session.post(login_url, data=payload, headers=headers)

    # Check SIS login
    if "login" in response.url:
        await ctx.send("Your ID/Password is invalid for SIS!")
        return

    # DigiVal Login
    payload_ = {'email': f"{student_id}@upm.edu.sa", 'password': digi_password, 'device_type': "web"}
    Login_url = "https://dsapi.produpm.digi-val.com/api/v1/digiclass/user/authLogin"
    login_response = Digi_session.post(Login_url, data=payload_).json()

    if not login_response['status']:
        await ctx.send("Your ID/Password is invalid for DigiVal!")
        return

    login_response = login_response['data']
    Digi_session.headers.update({
        'user-agent': 'Mozilla/5.0',
        '_user_id': login_response['_id'],
        'authorization': f"Bearer {login_response['tokens']['access']['token']}",
    })

    await ctx.send(f"Logged in successfully as {student_id}!")

@bot.command()
async def schedule(ctx):
    """Command to fetch and display the weekly schedule."""
    if not login_response:
        await ctx.send("Please log in first using the `/login` command.")
        return

    weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    week_dates = [(datetime.now().date() - timedelta(days=datetime.now().weekday() + 1) + timedelta(days=i)).isoformat() for i in range(5)]

    schedules = {}
    for i, day in enumerate(weekdays):
        url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/get-schedule-by-date/{login_response['_id']}/{week_dates[i]}T21:00:00Z?timeZone=Asia/Riyadh"
        response = Digi_session.get(url).json()
        schedules[day] = response.get('data', [])

    for day, lectures in schedules.items():
        schedule_msg = f"**{day} Schedule:**\n"
        if lectures:
            for lecture in lectures:
                course = lecture.get('course_code', '-')
                course_name = lecture.get('course_name', '-')
                start_time = f"{lecture['start']['hour']}:{lecture['start']['minute']}{lecture['start']['format']}"
                end_time = f"{lecture['end']['hour']}:{lecture['end']['minute']}{lecture['end']['format']}"
                schedule_msg += f"{course}: {course_name} ({start_time} - {end_time})\n"
        else:
            schedule_msg += "No classes scheduled.\n"
        await ctx.send(schedule_msg)

@bot.command()
async def advisor(ctx):
    """Command to fetch the academic advisor."""
    if not login_response:
        await ctx.send("Please log in first using the `/login` command.")
        return

    target_info = "https://sis.upm.edu.sa/psc/ps/EMPLOYEE/HRMS/c/SA_LEARNER_SERVICES.SSS_STUDENT_CENTER.GBL?NavColl=true&ICAGTarget=start"
    info = session.get(target_info)
    soup = BeautifulSoup(info.content, "html.parser")
    tree = etree.HTML(str(soup))
    advisor = tree.xpath('//*[@id="DERIVED_SSS_SCL_NAME_DISPLAY$span$0"]')

    if advisor:
        advisor_name = advisor[0].text
        await ctx.send(f"Your academic advisor is: {advisor_name}")
    else:
        await ctx.send("Unable to fetch advisor details.")

# Run the bot
bot.run("MTMyNDEyMjY4NTk1NzA3OTE1Mg.Gw3xTb.TN2Xxdw7VEl5a_jdfzFAmR3OrLfJZkXt4MBcJo")
