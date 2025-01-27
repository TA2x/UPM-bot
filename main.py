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

# File to store user data
USER_DATA_FILE = "user_data.json"
LOGGED_IN_USERS_FILE = "logged_in_users.json"

# Load or initialize user data
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as file:
        user_data = json.load(file)
else:
    user_data = {}

# Load or initialize logged-in users data
if os.path.exists(LOGGED_IN_USERS_FILE):
    with open(LOGGED_IN_USERS_FILE, "r") as file:
        logged_in_users = json.load(file)
else:
    logged_in_users = {}

# Save logged-in users data to file
def save_logged_in_users():
    with open(LOGGED_IN_USERS_FILE, "w") as file:
        json.dump(logged_in_users, file)

# Initialize Discord bot
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Global session objects
session = requests.Session()
Digi_session = requests.Session()
login_response = {}

# On ready, sync commands with the server
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()  # Sync slash commands
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print(f"Bot {bot.user} is online!")

# Define a slash command
@bot.tree.command(name="active-dev-badge", description="Show an active developer badge!")
async def active_dev_badge(interaction: discord.Interaction):
    # Custom response for the badge-like appearance
    embed = discord.Embed(
        title="Active Developer Badge",
        description="**You used the Active Developer Badge command! 🛠️**",
        color=discord.Color.blue()
    )
    embed.set_footer(text="testerSA APP")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1068576796805154916.png")  # Replace with your emoji/image URL

    await interaction.response.send_message(embed=embed)

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

    # Check if the user is already logged in
    if user_id in logged_in_users:
        await ctx.send("You are already logged in.")
        return

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
    login_response[user_id] = Digi_session.post(Login_url, data=payload_).json()

    if not login_response[user_id]['status']:
        await ctx.send("Your ID/Password is invalid for DigiVal!")
        return

    user_data[user_id].update({
        'Digi_id': login_response[user_id]['data']['_id'],
        'tokens': login_response[user_id]['data']['tokens']['access']['token']
    })

    Digi_session.headers.update({
        'user-agent': 'Mozilla/5.0',
        '_user_id': user_data[user_id]['Digi_id'],
        'authorization': f"Bearer {user_data[user_id]['tokens']}"
    })

    # Mark the user as logged in
    logged_in_users[user_id] = True
    save_logged_in_users()

    await ctx.send(f"Logged in successfully as {student_id}!")

@bot.command()
async def schedule(ctx):
    """Fetch and display the weekly schedule."""
    global login_response

    # Check if the user is logged in
    if not login_response:
        await ctx.send("⛔ Please log in first using the `/login` command.")
        return

    weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    today = datetime.now().date()
    week_dates = [
        (today - timedelta(days=today.weekday()) + timedelta(days=i)).isoformat()
        for i in range(5)
    ]

    user_id = login_response['_id']
    timezone = "Asia/Riyadh"
    base_url = "https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/get-schedule-by-date"
    schedules = {}
    for i, day in enumerate(weekdays):
        url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/get-schedule-by-date/{login_response['_id']}/{week_dates[i]}T21:00:00Z?timeZone=Asia/Riyadh"
        try:
            response = Digi_session.get(url)
            response.raise_for_status()
            day_data = response.json()
            schedules[day] = day_data.get('data', [])
        except requests.exceptions.RequestException as e:
            await ctx.send(f"⛔ Error fetching schedule for {day}: {e}")
            return

    for day, lectures in schedules.items():
        schedule_msg = f"**{day} Schedule:**\n"
        if lectures:
            for lecture in lectures:
                try:
                    course = lecture.get('course_code', 'Unknown Code')
                    course_name = lecture.get('course_name', 'Unknown Course')
                    start_time = f"{lecture['start']['hour']}:{lecture['start']['minute']}{lecture['start']['format']}"
                    end_time = f"{lecture['end']['hour']}:{lecture['end']['minute']}{lecture['end']['format']}"
                    schedule_msg += f"**{course}**: {course_name} ({start_time} - {end_time})\n"
                except KeyError as e:
                    schedule_msg += f"Error parsing lecture details: {e}\n"
        else:
            schedule_msg += "No classes scheduled.\n"

        # Split large messages into chunks to avoid hitting the 2000-character limit
        if len(schedule_msg) > 2000:
            for chunk in [schedule_msg[i:i+2000] for i in range(0, len(schedule_msg), 2000)]:
                await ctx.send(chunk)
        else:
            await ctx.send(schedule_msg)

@bot.command()
async def courses(ctx):
    """Fetches the courses for the student."""
    global login_responses
    user_id = str(ctx.author.id)

    # Check if user is logged in
    if user_id not in login_responses:
        await ctx.send("You need to log in first using the `/login` command.")
        return

    # URL to fetch courses
    courses_url = "https://digiclass.upm.digi-val.com/courses"

    try:
        # Make a GET request to fetch courses
        response = Digi_session.get(courses_url).json()
        
        if response.get('status', False):  # Check response status
            table_data = []
            for item in response.get('data', []):
                course_id = item.get('course_id', 'N/A')
                course_name = item.get('course_name', 'N/A')
                table_data.append([course_id, course_name])

            # Format the table and send it to the user
            table = tabulate(table_data, headers=['Course ID', 'Course Name'], tablefmt='grid')
            await ctx.send(f"```\n{table}\n```")  # Use code block for better formatting
        else:
            await ctx.send("Failed to fetch courses. Please try again later.")
    except Exception as e:
        # Handle any errors during the API call
        await ctx.send(f"Error fetching courses: {str(e)}")

@bot.command()
async def grades(ctx):
    """Fetches the student's grades."""
    global login_responses
    user_id = str(ctx.author.id)

    if user_id not in login_responses:
        await ctx.send("You need to log in first using the `/login` command.")
        return

    grades_url = r"https://sis.upm.edu.sa/psc/ps/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.SSR_SSENRL_GRADE.GBL?PortalActualURL=https%3a%2f%2fsis.upm.edu.sa%2fpsc%2fps%2fEMPLOYEE%2fSA%2fc%2fSA_LEARNER_SERVICES.SSR_SSENRL_GRADE.GBL&PortalContentURL=https%3a%2f%2fsis.upm.edu.sa%2fpsc%2fps%2fEMPLOYEE%2fSA%2fc%2fSA_LEARNER_SERVICES.SSR_SSENRL_GRADE.GBL&PortalContentProvider=SA&PortalCRefLabel=View%20My%20Grades&PortalRegistryName=EMPLOYEE&PortalServletURI=https%3a%2f%2fsis.upm.edu.sa%2fpsp%2fps%2f&PortalURI=https%3a%2f%2fsis.upm.edu.sa%2fpsc%2fps%2f&PortalHostNode=HRMS&NoCrumbs=yes&PortalKeyStruct=yes"  # Replace with actual grades endpoint
    
    info = session.get(grades_url)

    soup = BeautifulSoup(info.content, "html.parser")

    tree = etree.HTML(str(soup))
    try:
        response = Digi_session.get(grades_url).json()
        if response['status']:
            table_data = []
            for item in response['data']:
                course_name = item.get('course_name', 'N/A')
                grade = item.get('grade', 'N/A')
                table_data.append([course_name, grade])

            table = tabulate(table_data, headers=['Course', 'Grade'], tablefmt='grid')
            await ctx.send(f"```\n{table}\n```")
        else:
            await ctx.send("Failed to fetch grades. Please try again later.")
    except Exception as e:
        await ctx.send(f"Error fetching grades: {str(e)}")

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
async def attendance(ctx):
    """Command to fetch and display attendance."""
    user_id = str(ctx.author.id)

    if user_id not in logged_in_users:
        await ctx.send("Please log in first using the `/login` command.")
        return

    try:
        # Get the user's unique identifier
        user_data_response = Digi_session.get(f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/user/{login_response['_id']}/data")
        user_data = user_data_response.json()

        if not user_data:
            await ctx.send("No attendance data available.")
            return

        attendance_data = user_data.get('attendance', [])
        if attendance_data:
            for course in attendance_data:
                attended = course.get('attended', 0)
                total = course.get('total', 0)
                percentage = round((attended / total) * 100, 2) if total > 0 else 0
                await ctx.send(f"Course: {course['name']}\nAttended: {attended}\nTotal: {total}\nAttendance Percentage: {percentage}%")
        else:
            await ctx.send("No attendance records found.")
    except Exception as e:
        await ctx.send(f"An error occurred while fetching attendance: {str(e)}")

@bot.command()
async def exams(ctx):
    """Fetch and display the exam schedule."""
    user_id = str(ctx.author.id)

    if user_id not in logged_in_users:
        await ctx.send("Please log in first using the `/login` command.")
        return

    try:
        exam_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/user/{login_response['_id']}/exams"
        response = Digi_session.get(exam_url)
        exams = response.json().get('data', [])

        if not exams:
            await ctx.send("No exams found.")
            return

        exams_message = "**Exam Schedule:**\n"
        for exam in exams:
            exams_message += f"{exam['course_name']} - {exam['date']} at {exam['time']}\n"

        await ctx.send(exams_message)
    except Exception as e:
        await ctx.send(f"An error occurred while fetching exam schedule: {str(e)}")

@bot.command()
async def feedback(ctx, *, message):
    """Submit feedback to the Bot owner."""
    bot_owner_id = 360427220109623297
    bot_owner = await bot.fetch_user(bot_owner_id)

    try:
        await bot_owner.send(f"Feedback from {ctx.author.name}#{ctx.author.discriminator}:\n{message}")
        await ctx.send("Thank you for your feedback!")
    except Exception as e:
        await ctx.send(f"An error occurred while sending feedback: {str(e)}")
reminder_tasks = {}  # Dictionary to store active tasks for each user

@bot.command()
async def remind(ctx, time: int, *, reminder: str):
    """Set a reminder in minutes."""
    if time <= 0:
        await ctx.send("⛔ Please provide a valid time greater than 0.")
        return

    user_id = ctx.author.id
    channel_id = ctx.channel.id

    # Function to send the reminder
    async def send_reminder():
        await asyncio.sleep(time * 60)  # Wait for the specified time
        await ctx.send(f"⏰ **Reminder for <@{user_id}>:** {reminder}")
        # Remove the completed task from reminder_tasks
        if user_id in reminder_tasks:
            reminder_tasks[user_id] = [task for task in reminder_tasks[user_id] if not task.done()]

    # Create and start the reminder task
    task = asyncio.create_task(send_reminder())
    if user_id not in reminder_tasks:
        reminder_tasks[user_id] = []
    reminder_tasks[user_id].append(task)

    await ctx.send(f"⏳ Reminder set for {time} minutes: **{reminder}**")

@bot.command()
async def cancel_reminders(ctx):
    """Cancel all reminders for the user."""
    user_id = ctx.author.id

    if user_id not in reminder_tasks or not reminder_tasks[user_id]:
        await ctx.send("⛔ You have no active reminders to cancel.")
        return

    # Cancel all tasks for the user
    for task in reminder_tasks[user_id]:
        task.cancel()
    reminder_tasks[user_id] = []

    await ctx.send(f"✅ All your reminders have been canceled, <@{user_id}>.")

# Finish by running the bot
bot.run("MTMyNDEyMjY4NTk1NzA3OTE1Mg.Gw3xTb.TN2Xxdw7VEl5a_jdfzFAmR3OrLfJZkXt4MBcJo")
