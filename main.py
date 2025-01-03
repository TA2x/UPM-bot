import discord
from discord.ext import commands
from discord import app_commands
from termcolor import colored
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from colorama import Fore, Style, init
from datetime import datetime, timedelta
import requests
import pyfiglet
import json
import os
import asyncio
from discord import app_commands

# File to store user data
USER_DATA_FILE = "user_data.json"

# Load or initialize user data
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as file:
        user_data = json.load(file)
else:
    user_data = {}

# Initialize Discord bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global session objects
session = requests.Session()
Digi_session = requests.Session()
login_response = None

@app_commands.command(name="test", description="A test command")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Hello! This is a test command.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")

# Add to bot tree
@bot.event
async def on_ready():
    bot.tree.add_command(test)  # Register the command
    await bot.tree.sync()  # Sync to the server
    print("Commands synced successfully.")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("Pong!")

@bot.event
async def on_message(message):
    """Handle messages to check for user login information."""
    if message.author.bot:
        return

    user_id = str(message.author.id)

    # Check if user info is already saved
    if user_id not in user_data:
        try:
            # Send a DM asking for login info
            dm_channel = await message.author.create_dm()
            await dm_channel.send("Hi! Please provide your login info. Reply with the following format: `student_id,password,digi_password`")

            # Wait for user response
            def check(msg):
                return msg.author == message.author and isinstance(msg.channel, discord.DMChannel)

            try:
                login_msg = await bot.wait_for('message', check=check, timeout=120)  # 2-minute timeout
                login_info = login_msg.content.split(",")

                if len(login_info) != 3:
                    await dm_channel.send("Invalid format. Please use the format: `student_id,password,digi_password`.")
                    return

                # Save user info
                user_data[user_id] = {
                    "student_id": login_info[0],
                    "password": login_info[1],
                    "digi_password": login_info[2]
                }
                with open(USER_DATA_FILE, "w") as file:
                    json.dump(user_data, file)

                await dm_channel.send("Thank you! Your info has been saved.")
            except asyncio.TimeoutError:
                await dm_channel.send("You took too long to respond. Please try again later.")
        except Exception as e:
            await message.channel.send(f"Failed to send a DM: {str(e)}")

    await bot.process_commands(message)

@bot.command()
async def login(ctx, student_id: str = None, password: str = None, digi_password: str = None):
    """Command to log in and establish sessions."""
    global login_response

    user_id = str(ctx.author.id)

    # Use saved login info if available
    if user_id in user_data and not (student_id and password and digi_password):
        student_id = user_data[user_id]["student_id"]
        password = user_data[user_id]["password"]
        digi_password = user_data[user_id]["digi_password"]

    if not (student_id and password and digi_password):
        await ctx.send("Please provide your login info using `/login student_id password digi_password`.")
        return

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

@bot.command()
async def grades(ctx):
    """Fetch and display grades for the user."""
    if not login_response:
        await ctx.send("Please log in first using the `/login` command.")
        return

    grades_url = "https://sis.upm.edu.sa/path/to/grades/endpoint"
    response = session.get(grades_url)
    
    if response.status_code == 200:
        grades_data = response.json()
        # Process grades and format a message
        grades_message = "Here are your grades:\n"
        for course in grades_data:
            grades_message += f"{course['course_code']} - {course['course_name']}: {course['grade']}\n"
        await ctx.send(grades_message)
    else:
        await ctx.send("Unable to fetch grades at the moment.")

@bot.command()
async def announcements(ctx):
    """Fetch and display recent announcements."""
    announcements_url = "https://sis.upm.edu.sa/path/to/announcements/endpoint"
    response = session.get(announcements_url)

    if response.status_code == 200:
        announcements = response.json()
        message = "**Recent Announcements:**\n"
        for announcement in announcements:
            message += f"- {announcement['title']}: {announcement['date']}\n{announcement['description']}\n"
        await ctx.send(message)
    else:
        await ctx.send("Unable to fetch announcements.")

@bot.command()
async def attendance(ctx):
    """Command to fetch and display attendance."""
    if not login_response:
        await ctx.send("Please log in first using the `/login` command.")
        return

    user_id = login_response['_id']

    try:
        # Get the calendar ID
        url_calendar = f'https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCalendars/{user_id}/student'
        calendar_response = Digi_session.get(url_calendar)
        calendar_id = calendar_response.json().get('data', [{}])[0].get('_id')

        # Get program IDs
        programs_ids_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourses/{user_id}?institutionCalendarId={calendar_id}&type=student"
        programs_response = Digi_session.get(programs_ids_url).json().get('data', [])
        programs_ids = [[p['_id'], p['_program_id'], p['course_code']] for p in programs_response]

        def calculate_percentage(num1, num2):
            return round((num1 / num2) * 100, 2) if num2 != 0 else None

        # Fetch attendance details for each program
        for program in programs_ids:
            program_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourseSessionDetails/{user_id}/{program[0]}?institutionCalendarId={calendar_id}&type=student&level=Level%201&term=Fall-spring-summer&programId={program[1]}&year=year1"
            program_data = Digi_session.get(program_url).json().get('data', {})

            # Retry with different term if data is not found
            if not program_data.get('maleStudentCount'):
                program_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourseSessionDetails/{user_id}/{program[0]}?institutionCalendarId={calendar_id}&type=student&level=Level%201&term=Regular&programId={program[1]}&year=year1"
                program_data = Digi_session.get(program_url).json().get('data', {})

            if program_data:
                # Extract attendance details
                course_code = program[2]
                attended_sessions = program_data.get('attendedSessions', 0)
                completed_sessions = program_data.get('completedSessions', 0)
                absent_count = program_data.get('absentCount', 0)
                total_sessions = program_data.get('totalSessions', 0)

                # Calculate percentages
                attendance_percentage = calculate_percentage(attended_sessions, completed_sessions)
                absence_percentage = round(absent_count / total_sessions * 100, 2) if total_sessions else 0

                # Send attendance details to Discord
                attendance_message = (
                    f"**Course Code: {course_code}**\n"
                    f"You attended **{attended_sessions}** out of **{completed_sessions}** sessions.\n"
                    f"You missed **{absent_count}** sessions.\n"
                    f"Your attendance percentage is **{attendance_percentage}%**.\n"
                    f"Your absence percentage is **{absence_percentage}%**.\n"
                    f"------------------------------"
                )
                await ctx.send(attendance_message)
            else:
                await ctx.send(f"Error fetching data for program {program[2]}.")
    except Exception as e:
        await ctx.send(f"An error occurred while fetching attendance: {str(e)}")

@bot.command()
async def feedback(ctx, *, message):
    """Submit feedback to the Bot owner."""
    bot_owner_id = 360427220109623297  # Replace this with your Discord ID
    bot_owner = await bot.fetch_user(bot_owner_id)  # Fetch the bot owner's user object
    
    # Send the feedback message to the bot owner
    await bot_owner.send(f"Feedback from {ctx.author.name}#{ctx.author.discriminator}:\n{message}")
    
    # Notify the user that their feedback was received
    await ctx.send("Thank you for your feedback!")

@bot.command()
async def exams(ctx):
    """Fetch and display exam schedule."""
    if not login_response:
        await ctx.send("Please log in first using the `/login` command.")
        return

    exams_url = "https://sis.upm.edu.sa/psp/ps/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.SSR_SSENRL_EXAM_L.GBL"
    response = session.get(exams_url)

    if response.status_code == 200:
        exams = response.json()
        exams_msg = "**Exam Schedule:**\n"
        for exam in exams:
            exams_msg += f"{exam['course_code']} - {exam['date']} at {exam['time']}\n"
        await ctx.send(exams_msg)
    else:
        await ctx.send("Unable to fetch exam schedule.")

reminders = {}

@bot.command()
async def remind(ctx, time: int, *, reminder):
    """Set a reminder in minutes."""
    await ctx.send(f"Reminder set for {time} minutes: {reminder}")
    reminders[ctx.author.id] = (time, reminder)

    await asyncio.sleep(time * 60)
    await ctx.send(f"⏰ Reminder: {reminder}")

# Run the bot
bot.run("MTMyNDEyMjY4NTk1NzA3OTE1Mg.Gw3xTb.TN2Xxdw7VEl5a_jdfzFAmR3OrLfJZkXt4MBcJo")
