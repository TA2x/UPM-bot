import discord
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup
from lxml import etree
from datetime import datetime, timedelta
import requests
import json
import os
import asyncio
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

# File paths
USER_DATA_FILE = "user_data.json"
LOGGED_IN_USERS_FILE = "logged_in_users.json"

# Load or initialize data stores
user_data = {}
logged_in_users = {}
user_sessions = {}  # Stores individual user sessions

try:
    with open(USER_DATA_FILE, "r") as f:
        user_data = json.load(f)
except FileNotFoundError:
    pass

try:
    with open(LOGGED_IN_USERS_FILE, "r") as f:
        logged_in_users = json.load(f)
except FileNotFoundError:
    pass

# Initialize bot with proper intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

def save_data():
    """Save all persistent data"""
    with open(USER_DATA_FILE, "w") as f:
        json.dump(user_data, f)
    with open(LOGGED_IN_USERS_FILE, "w") as f:
        json.dump(logged_in_users, f)

@bot.event
async def on_ready():
    """Handle bot startup"""
    print(f"✅ Bot ready as {bot.user.name} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ Command sync error: {e}")

@bot.event
async def on_message(message):
    """Handle login info collection"""
    if message.author.bot or not isinstance(message.channel, discord.DMChannel):
        await bot.process_commands(message)
        return

    user_id = str(message.author.id)
    
    try:
        if user_id not in user_data:
            await message.author.send("🔑 Please send your credentials in format: `student_id,password,digi_password`")
            
            def check(m):
                return m.author == message.author and isinstance(m.channel, discord.DMChannel)
            
            try:
                creds = await bot.wait_for('message', check=check, timeout=120)
                student_id, password, digi_password = creds.content.strip().split(',')
                
                user_data[user_id] = {
                    "student_id": student_id,
                    "password": password,
                    "digi_password": digi_password
                }
                save_data()
                await message.author.send("✅ Credentials saved securely")
                
            except asyncio.TimeoutError:
                await message.author.send("⌛ Timeout: Please try again later")
            except ValueError:
                await message.author.send("❌ Invalid format. Use: student_id,password,digi_password")
    
    except Exception as e:
        logging.error(f"DM error: {str(e)}")
    
    await bot.process_commands(message)

@bot.command()
async def login(ctx):
    """User login handler"""
    user_id = str(ctx.author.id)
    
    if user_id in logged_in_users:
        await ctx.send("⚠️ You're already logged in!")
        return
    
    try:
        creds = user_data.get(user_id)
        if not creds:
            await ctx.send("❌ No credentials found. Send them via DM first")
            return
        
        # Create individual sessions
        user_sessions[user_id] = {
            "sis": requests.Session(),
            "digi": requests.Session(),
            "data": None
        }
        
        # SIS Login
        sis_login = user_sessions[user_id]["sis"].post(
            "https://sis.upm.edu.sa/psp/ps/?=&cmd=login&languageCd=ENG",
            data={"userid": creds["student_id"], "pwd": creds["password"]},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if "login" in sis_login.url:
            await ctx.send("❌ Invalid SIS credentials")
            return
        
        # DigiVal Login
        digi_login = user_sessions[user_id]["digi"].post(
            "https://dsapi.produpm.digi-val.com/api/v1/digiclass/user/authLogin",
            data={
                "email": f"{creds['student_id']}@upm.edu.sa",
                "password": creds["digi_password"],
                "device_type": "web"
            }
        ).json()
        
        if not digi_login.get('status'):
            await ctx.send("❌ Invalid DigiVal credentials")
            return
        
        # Store session data
        user_sessions[user_id]["data"] = digi_login['data']
        user_sessions[user_id]["digi"].headers.update({
            "authorization": f"Bearer {digi_login['data']['tokens']['access']['token']}",
            "_user_id": digi_login['data']['_id']
        })
        
        logged_in_users[user_id] = True
        save_data()
        await ctx.send(f"✅ Logged in as {creds['student_id']}")
        
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        await ctx.send("🔴 Login failed - contact support")

@bot.command()
async def logout(ctx):
    """User logout handler"""
    user_id = str(ctx.author.id)
    
    if user_id in logged_in_users:
        # Clear all session data
        user_sessions.pop(user_id, None)
        logged_in_users.pop(user_id, None)
        save_data()
        await ctx.send("✅ Logged out successfully")
    else:
        await ctx.send("⚠️ You're not logged in")

@bot.command()
async def schedule(ctx):
    """Get class schedule"""
    user_id = str(ctx.author.id)
    
    if user_id not in logged_in_users:
        await ctx.send("🔒 Please login first")
        return
    
    try:
        # Date calculations
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday() + 1)
        dates = [(week_start + timedelta(days=i)).date().isoformat() for i in range(5)]
        
        schedule_data = {}
        digi_session = user_sessions[user_id]["digi"]
        user_id_digi = user_sessions[user_id]["data"]["_id"]
        
        for i, date in enumerate(dates):
            url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/get-schedule-by-date/{user_id_digi}/{date}T21:00:00Z?timeZone=Asia/Riyadh"
            response = digi_session.get(url).json()
            schedule_data[date] = response.get('data', [])
        
        # Format and send schedule
        for date, classes in schedule_data.items():
            msg = f"📅 **{datetime.fromisoformat(date).strftime('%A')} Schedule**\n"
            if classes:
                for cls in classes:
                    msg += (
                        f"⏰ {cls['start']['hour']}:{cls['start']['minute']}{cls['start']['format']} - "
                        f"{cls['end']['hour']}:{cls['end']['minute']}{cls['end']['format']}\n"
                        f"📚 {cls.get('course_code', 'N/A')} - {cls.get('course_name', 'Unnamed')}\n\n"
                    )
            else:
                msg += "🎉 No classes scheduled!\n"
            
            await ctx.send(msg[:2000])  # Respect Discord's message limit
            
    except Exception as e:
        logging.error(f"Schedule error: {str(e)}")
        await ctx.send("❌ Failed to fetch schedule")

@bot.command()
async def advisor(ctx):
    """Fetch academic advisor"""
    user_id = str(ctx.author.id)
    
    if user_id not in logged_in_users:
        await ctx.send("🔒 Please login first")
        return
    
    try:
        sis_session = user_sessions[user_id]["sis"]
        target_info = "https://sis.upm.edu.sa/psc/ps/EMPLOYEE/HRMS/c/SA_LEARNER_SERVICES.SSS_STUDENT_CENTER.GBL?NavColl=true&ICAGTarget=start"
        info = sis_session.get(target_info)
        soup = BeautifulSoup(info.content, "html.parser")
        tree = etree.HTML(str(soup))
        advisor = tree.xpath('//*[@id="DERIVED_SSS_SCL_NAME_DISPLAY$span$0"]')

        if advisor:
            advisor_name = advisor[0].text
            await ctx.send(f"👨‍🏫 Your academic advisor is: {advisor_name}")
        else:
            await ctx.send("❌ Unable to fetch advisor details")
            
    except Exception as e:
        logging.error(f"Advisor error: {str(e)}")
        await ctx.send("❌ Failed to fetch advisor")

@bot.command()
async def attendance(ctx):
    """Fetch attendance records"""
    user_id = str(ctx.author.id)
    
    if user_id not in logged_in_users:
        await ctx.send("🔒 Please login first")
        return
    
    try:
        digi_session = user_sessions[user_id]["digi"]
        user_id_digi = user_sessions[user_id]["data"]["_id"]
        
        # Get calendar ID
        url_calendar = f'https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCalendars/{user_id_digi}/student'
        calendar_response = digi_session.get(url_calendar)
        calendar_id = calendar_response.json().get('data', [{}])[0].get('_id')

        # Get program IDs
        programs_ids_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourses/{user_id_digi}?institutionCalendarId={calendar_id}&type=student"
        programs_response = digi_session.get(programs_ids_url).json().get('data', [])
        programs_ids = [[p['_id'], p['_program_id'], p['course_code']] for p in programs_response]

        def calculate_percentage(num1, num2):
            return round((num1 / num2) * 100, 2) if num2 != 0 else None

        # Fetch attendance details for each program
        for program in programs_ids:
            program_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourseSessionDetails/{user_id_digi}/{program[0]}?institutionCalendarId={calendar_id}&type=student&level=Level%201&term=Fall-spring-summer&programId={program[1]}&year=year1"
            program_data = digi_session.get(program_url).json().get('data', {})

            # Retry with different term if data is not found
            if not program_data.get('maleStudentCount'):
                program_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourseSessionDetails/{user_id_digi}/{program[0]}?institutionCalendarId={calendar_id}&type=student&level=Level%201&term=Regular&programId={program[1]}&year=year1"
                program_data = digi_session.get(program_url).json().get('data', {})

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
                    f"📊 **Course Code: {course_code}**\n"
                    f"✅ Attended: **{attended_sessions}** out of **{completed_sessions}** sessions\n"
                    f"❌ Missed: **{absent_count}** sessions\n"
                    f"📈 Attendance: **{attendance_percentage}%**\n"
                    f"📉 Absence: **{absence_percentage}%**\n"
                    f"------------------------------"
                )
                await ctx.send(attendance_message)
            else:
                await ctx.send(f"❌ Error fetching data for program {program[2]}")
                
    except Exception as e:
        logging.error(f"Attendance error: {str(e)}")
        await ctx.send("❌ Failed to fetch attendance")

@bot.command()
async def feedback(ctx, *, message):
    """Submit feedback to the bot owner"""
    bot_owner_id = 360427220109623297  # Replace with your Discord ID
    bot_owner = await bot.fetch_user(bot_owner_id)
    
    try:
        await bot_owner.send(f"📩 Feedback from {ctx.author.name}#{ctx.author.discriminator}:\n{message}")
        await ctx.send("✅ Thank you for your feedback!")
    except Exception as e:
        logging.error(f"Feedback error: {str(e)}")
        await ctx.send("❌ Failed to send feedback")

@bot.command()
async def exams(ctx):
    """Fetch exam schedule"""
    user_id = str(ctx.author.id)
    
    if user_id not in logged_in_users:
        await ctx.send("🔒 Please login first")
        return
    
    try:
        sis_session = user_sessions[user_id]["sis"]
        exams_url = "https://sis.upm.edu.sa/psp/ps/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.SSR_SSENRL_EXAM_L.GBL"
        response = sis_session.get(exams_url)

        if response.status_code == 200:
            exams = response.json()
            exams_msg = "📝 **Exam Schedule:**\n"
            for exam in exams:
                exams_msg += f"📅 {exam['course_code']} - {exam['date']} at {exam['time']}\n"
            await ctx.send(exams_msg)
        else:
            await ctx.send("❌ Unable to fetch exam schedule")
            
    except Exception as e:
        logging.error(f"Exams error: {str(e)}")
        await ctx.send("❌ Failed to fetch exam schedule")

@bot.command()
async def remind(ctx, time: int, *, reminder):
    """Set a reminder"""
    try:
        await ctx.send(f"⏰ Reminder set for {time} minutes: {reminder}")
        await asyncio.sleep(time * 60)
        await ctx.send(f"🔔 Reminder: {reminder}")
    except Exception as e:
        logging.error(f"Reminder error: {str(e)}")
        await ctx.send("❌ Failed to set reminder")

# Run the bot
bot.run("MTMyNDEyMjY4NTk1NzA3OTE1Mg.Gw3xTb.TN2Xxdw7VEl5a_jdfzFAmR3OrLfJZkXt4MBcJo")  # Replace with your actual token