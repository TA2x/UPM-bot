from termcolor import colored
from bs4 import BeautifulSoup
from lxml import etree
from tabulate import tabulate
from colorama import Fore, Back, Style, init
from datetime import datetime, timedelta

import pyfiglet.fonts
import requests
import msvcrt
import os
import re
import time
import pyfiglet

os.system("cls")

# Helper function
def get_password(message):
    password = ""
    print(message, end="", flush=True)
    while True:
        char = msvcrt.getch()
        if char == b'\r':  
            print()  
            break
        elif char == b'\x08': 
            if password:
                password = password[:-1]
                print('\b \b', end='', flush=True)
        else:
            password += char.decode('utf-8')
            print('*', end='', flush=True)
    return password

# ===============


session = requests.session()
student_id = input("Enter your student ID: ")
password = get_password("Enter your SIS Password: ")
digi_password = get_password("Enter your DigiVal Password: ")

login_url = "https://sis.upm.edu.sa/psp/ps/?=&cmd=login&languageCd=ENG"
payload = {"userid": student_id,"pwd": password,}
headers = {'User-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19582'}
response = session.post(login_url, data=payload, headers=headers)


# Digi Session ===============
payload_ = {'email': f"{student_id}@upm.edu.sa", 'password': digi_password, 'device_type': "web"}
Login_url = "https://dsapi.produpm.digi-val.com/api/v1/digiclass/user/authLogin"
Digi_session = requests.Session()
login_response = Digi_session.post(Login_url, data=payload_)

if not login_response.json()['status']:
    print(colored("Your ID/Password is invalid for the DigiVal !", 'red'))
    exit()

login_response = login_response.json()['data']
Digi_session.headers.update({
    'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    '_user_id': login_response['_id'],
    'authorization': f"Bearer {login_response['tokens']['access']['token']}",
})
# Digi Session End ===============



def GetUsername():
    target_info = "https://sis.upm.edu.sa/psc/ps/EMPLOYEE/HRMS/c/MAINTAIN_SECURITY.USERMAINT_SELF.GBL?PortalActualURL=https://sis.upm.edu.sa/psc/ps/EMPLOYEE/HRMS/c/MAINTAIN_SECURITY.USERMAINT_SELF.GBL&PortalContentURL=https://sis.upm.edu.sa/psc/ps/EMPLOYEE/HRMS/c/MAINTAIN_SECURITY.USERMAINT_SELF.GBL&PortalContentProvider=HRMS&PortalCRefLabel=My System Profile&PortalRegistryName=EMPLOYEE&PortalServletURI=https://sis.upm.edu.sa/psp/ps/&PortalURI=https://sis.upm.edu.sa/psc/ps/&PortalHostNode=HRMS&NoCrumbs=yes&PortalKeyStruct=yes"

    info = session.get(target_info)

    soup = BeautifulSoup(info.content, "html.parser")

    tree = etree.HTML(str(soup))
    name = tree.xpath('//*[@id="PSUSRPRFL_WRK_PT_TEXT254"]/text()')
    return name[0]

# Check Credentials
if re.search("login", response.url):
    print(colored("\nYour ID/Password is invalid!\n", 'red'))
    exit()
else:
    print(colored("\nLogged In Successfully!", 'green'))
    time.sleep(1)
    os.system("cls")
    print(colored(f"Welcome, {GetUsername()}!", 'green'))
    print("="*30)
   
    
# Login above
# ------------------------------
# Main code down

# Schdule
weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Sunday']
def get_week_dates():
    current_date = datetime.now().date()
    current_day = current_date.weekday()  

    result_dates = []

    if current_day < 4: 
        sunday = current_date - timedelta(days=current_day + 1) 
        for i in range(5):  
            result_dates.append(sunday + timedelta(days=i)  + timedelta(days=-1))
    else: 
        sunday = current_date + timedelta(days=(6 - current_day)) 
        for i in range(5):
            result_dates.append(sunday + timedelta(days=i) + timedelta(days=-1))

    return result_dates

def week_day(d):
    main_list = Digi_session.get(f'https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/get-schedule-by-date/{login_response['_id']}/{get_week_dates()[d]}T21:00:00Z?timeZone=Asia/Riyadh').json()

    listt = []
    for lecture in main_list['data']:
        try:
            course = lecture['course_code']
        except KeyError:
            course = "-"

        try:
            course_fullName = lecture['course_name']
        except KeyError:
            course_fullName = '-'

        try: 
            course_type = lecture['session']['delivery_symbol']
        except KeyError: 
            course_type = '-'

        try:
            if lecture['_infra_id']:
                room = lecture['_infra_id']['room_no']
            else:
                room = lecture['infra_name']
        except KeyError:
            room = '-'

        try:
            start_time = f"{lecture['start']['hour']}:{lecture['start']['minute']}{lecture['start']['format']}"
        except KeyError:
            start_time = '-'

        try:
            end_time = f"{lecture['end']['hour']}:{lecture['end']['minute']}{lecture['end']['format']}"
        except KeyError:
            end_time = '-'

        try:
            doctor = f"{lecture['staffs'][0]['staff_name']['first']} {lecture['staffs'][0]['staff_name']['last']}"
        except KeyError:
            doctor = '-'
        
        listt.append(
            {"course_code": course, "course_name": course_fullName, "delivery_symbol": course_type, "start_time": start_time, "end_time": end_time, "room": room, "doctor": doctor}
        )    
        
    return listt

def print_schedule():
    print('Please wait a moment ...')
    # Schedule data containers for each day
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    schedules = {
        'Sunday': week_day(0),
        'Monday': week_day(1),
        'Tuesday': week_day(2),
        'Wednesday': week_day(3),
        'Thursday': week_day(4),
    }

    # Store the headers for the table without background colors
    headers = ["Course Code", "Course Name", "Session Type", "Time", "Room", "Doctor"]
    
    # Loop through each day and print its schedule separately
    for day in days:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{day} Schedule{Style.RESET_ALL}:")
        
        # Prepare the schedule data for this day
        table_data = []
        for idx, lecture in enumerate(schedules[day]):
            course = f"{Fore.GREEN}{lecture['course_code']}{Style.RESET_ALL}"
            course_fullName = f"{Fore.GREEN}{lecture['course_name']}{Style.RESET_ALL}"
            course_type = f"{Fore.GREEN}{lecture['delivery_symbol']}{Style.RESET_ALL}"
            room = f"{Fore.MAGENTA}{lecture['room']}{Style.RESET_ALL}"
            start_time = f"{Fore.BLUE}{lecture['start_time']}{Style.RESET_ALL}"
            end_time = f"{Fore.BLUE}{lecture['end_time']}{Style.RESET_ALL}"
            doctor = f"{Fore.RED}{lecture['doctor']}{Style.RESET_ALL}"

            # Add the row to the table data
            table_data.append([course, course_fullName, course_type,  f"{start_time} - {end_time}", room, doctor])
        
        # Print the schedule for the day as a table
        if table_data:  # Only print the table if there are classes for the day
            print(tabulate(table_data, headers=headers, tablefmt="fancy_grid", numalign="center", stralign="center"))
        else:
            print(f"{Fore.YELLOW}No classes scheduled.{Style.RESET_ALL}")            
            
# ============================================

def fetch_and_print_attendance(session, login_response):
    # Initialize colorama
    init(autoreset=True)

    user_id = login_response['_id']

    url_calendr = f'https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCalendars/{user_id}/student'
    calendr = session.get(url_calendr)
    calendr_id = calendr.json().get('data', [{}])[0].get('_id')

    programs_ids_url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourses/{user_id}?institutionCalendarId={calendr_id}&type=student"
    programs_ids_req = session.get(programs_ids_url).json().get('data', [])
    
    programs_ids = [[id_['_id'], id_['_program_id'], id_['course_code']] for id_ in programs_ids_req]

    def calculate_percentage(num1, num2):
        return round((num1 / num2) * 100, 2) if num2 != 0 else None

    for program in programs_ids:
        url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourseSessionDetails/{user_id}/{program[0]}?institutionCalendarId={calendr_id}&type=student&level=Level%201&term=Fall-spring-summer&programId={program[1]}&year=year1"
        program_data = session.get(url).json().get('data', {})

        if not program_data.get('maleStudentCount'):
            url = f"https://dsapi.produpm.digi-val.com/api/v1/digiclass/course_session/userCourseSessionDetails/{user_id}/{program[0]}?institutionCalendarId={calendr_id}&type=student&level=Level%201&term=Regular&programId={program[1]}&year=year1"
            program_data = session.get(url).json().get('data', {})

        if program_data:
            male_student_count = program_data.get('maleStudentCount', 'N/A')
            absentCount = program_data.get('absentCount', 0)
            attendedSessions = program_data.get('attendedSessions', 0)
            completedSessions = program_data.get('completedSessions', 0)
            totalSessions = program_data.get('totalSessions', 0)

            print(f"{Fore.YELLOW}Course Code: {program[2]}")
            print(f"{Fore.GREEN}You attended ({attendedSessions}) out of ({completedSessions}) Sessions  -  You missed ({absentCount}) Sessions")
            attendance_percentage = calculate_percentage(int(attendedSessions), int(completedSessions))
            print(f"{Fore.CYAN}Your attendance percentage is {attendance_percentage}%")
            if not int(totalSessions) == 0:
                absence_percentage = round(int(absentCount) / int(totalSessions) * 100, 2)
            else:
                absence_percentage = 0
            print(f"{Fore.RED}Absence percentage: {absence_percentage}%")
            print(Style.BRIGHT + "=" * 30)
        else:
            print(f"{Fore.RED}Error fetching data for program {program[2]}")
            print(Style.BRIGHT + "=" * 30)

def GetAdvisor():
    target_info = "https://sis.upm.edu.sa/psc/ps/EMPLOYEE/HRMS/c/SA_LEARNER_SERVICES.SSS_STUDENT_CENTER.GBL?NavColl=true&ICAGTarget=start"

    info = session.get(target_info)

    soup = BeautifulSoup(info.content, "html.parser")

    tree = etree.HTML(str(soup))
    advisor = tree.xpath('//*[@id="DERIVED_SSS_SCL_NAME_DISPLAY$span$0"]')

    advisorSplit = advisor[0].text.split(' ')

    partsToRemove = ["Mr", "Mrs", "Dr", "Prof"]
    for i in partsToRemove:
        if i in advisorSplit:
            advisorSplit.remove(i)

    email = advisorSplit[0][0].lower() + "." + advisorSplit[len(advisorSplit) - 1].lower() + "@upm.edu.sa"
    
    result = f"""
    Your academic advisor is: {colored(advisor[0].text, 'light_blue')}
    Email: {colored(email, 'light_blue')}"""
    return result

def major():
    target_info = "https://sis.upm.edu.sa/psc/ps/EMPLOYEE/HRMS/c/SA_LEARNER_SERVICES.SSR_SSADVR.GBL?PortalActualURL=https%3a%2f%2fsis.upm.edu.sa%2fpsc%2fps%2fEMPLOYEE%2fHRMS%2fc%2fSA_LEARNER_SERVICES.SSR_SSADVR.GBL&PortalContentURL=https%3a%2f%2fsis.upm.edu.sa%2fpsc%2fps%2fEMPLOYEE%2fHRMS%2fc%2fSA_LEARNER_SERVICES.SSR_SSADVR.GBL&PortalContentProvider=HRMS&PortalCRefLabel=My%20Advisors&PortalRegistryName=EMPLOYEE&PortalServletURI=https%3a%2f%2fsis.upm.edu.sa%2fpsp%2fps%2f&PortalURI=https%3a%2f%2fsis.upm.edu.sa%2fpsc%2fps%2f&PortalHostNode=HRMS&NoCrumbs=yes&PortalKeyStruct=yes"

    info = session.get(target_info)

    soup = BeautifulSoup(info.content, features="lxml")

    tree = etree.HTML(str(soup))

    major = tree.xpath('//*[@id="ACAD_PLAN_TBL_DESCR$0"]')

    return f"\n    Your Program Is:  {colored(major[0].text, "light_blue")}"

def GetSemesterHours():
    try:
        target_info = "https://sis.upm.edu.sa/psc/ps/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.SSR_SSENRL_GRADE.GBL?PortalActualURL=https://sis.upm.edu.sa/psc/ps/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.SSR_SSENRL_GRADE.GBL&PortalContentURL=https://sis.upm.edu.sa/psc/ps/EMPLOYEE/SA/c/SA_LEARNER_SERVICES.SSR_SSENRL_GRADE.GBL&PortalContentProvider=SA&PortalCRefLabel=View My Grades&PortalRegistryName=EMPLOYEE&PortalServletURI=https://sis.upm.edu.sa/psp/ps/&PortalURI=https://sis.upm.edu.sa/psc/ps/&PortalHostNode=HRMS&NoCrumbs=yes&PortalKeyStruct=yes"

        info = session.get(target_info)

        soup = BeautifulSoup(info.content, "html.parser")
        tree = etree.HTML(str(soup))

        hours = tree.xpath('//*[@id="STATS_ENRL$4"]/text()')
        resultHours = colored(re.sub(r'\..*', "", hours[0]) + " Hours", 'light_blue')

        print(f"    Your hours in this semester are: {resultHours}")

    except IndexError:
        print(colored("    Error: Can't retrieve hours for Prep Year Students!", 'red'))


# Options
while True:
    print("""  
    [1] - Weekly Schedule
    [2] - Acadamic Advisor
    [3] - Academic Program
    [4] - Semester Hours
    [5] - Get Your Attendance
    [6] - Credits
    [7] - Exit
    """, end='')
    choice = input("Please select your choice: ")

    if choice == '1':
        print()
        print_schedule()
        
    elif choice == '2':
        print(GetAdvisor())
    
    elif choice == '3': 
        print(major())
    
    elif choice == '4':
        print()
        GetSemesterHours()
        
    elif choice == '5':
        print()
        fetch_and_print_attendance(Digi_session, login_response)

    elif choice == '6':
        print(Fore.LIGHTGREEN_EX + pyfiglet.figlet_format("Credits", font="starwars") + Style.RESET_ALL)
        print(Back.LIGHTCYAN_EX + Fore.BLACK + "Yousef Mahmoud Aldarraj - 4510449" + Style.RESET_ALL)
        print(Back.LIGHTCYAN_EX + Fore.BLACK + "Mohammad Telad Haki - 4510328" + Style.RESET_ALL)
        print(Back.LIGHTCYAN_EX + Fore.BLACK + "Faisal Waleed Dawoud - 4510011" + Style.RESET_ALL)


    elif choice == '7':
        print(colored("\n    See you next time!\n", 'green'))
        exit()

    else:
        print(colored("\n    Please enter a valid choice", 'red'))