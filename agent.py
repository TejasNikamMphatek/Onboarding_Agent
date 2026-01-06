
import os
import json
import requests
from datetime import datetime
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import time



from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")
EXCLUDE_EMAILS = ["hr@mphatek.com", "admin@mphatek.com", "administrator"]

FRAPPE_URL = "http://localhost:8000"

HF_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

API_KEY = os.getenv("FRAPPE_API_KEY")
API_SECRET = os.getenv("FRAPPE_API_SECRET")

assert HF_API_KEY, "HUGGINGFACE_API_KEY missing"

assert API_KEY, "FRAPPE_API_KEY missing"
assert API_SECRET, "FRAPPE_API_SECRET missing"





llama_llm = LLM(
    model="huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
    api_key=HF_API_KEY,
    base_url="https://router.huggingface.co/v1",
    temperature=0.0,
    max_tokens=512,
)


headers = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json"
}

# === 2. HELPER FUNCTIONS ===
# Inside agent.py
def ask_human(field_label, user_id, default=""):
    from agent_fastapi import answers
    import time
    import requests

    cache_key = f"{user_id}_{field_label.replace(' ', '_')}"

    if cache_key in answers:
        del answers[cache_key]

    try:
        requests.post(
            f"{FRAPPE_URL}/api/method/hrms.hr.page.pipal_hr_dashboard.pipal_hr_dashboard.trigger_agent_popup",
            json={"field": field_label, "user_id": user_id, "cache_key": cache_key},
            headers=headers,
            timeout=5
        )
    except:
        print(f"⚠️ Could not reach Frappe for {field_label}")

    print(f"⌛ Waiting for HR to answer: {field_label}...")

    timeout = 300  # 5 minutes
    start = time.time()

    while cache_key not in answers:
        if time.time() - start > timeout:
            print(f"⏱️ Timeout waiting for {field_label}, using default")
            return default
        time.sleep(1)

    return answers.pop(cache_key)

# def ask_human(field_label, user_id, default=""):
#     from agent_fastapi import answers # Shared Dictionary
#     import time
#     import requests

#     cache_key = f"{user_id}_{field_label.replace(' ', '_')}"
    
#     # Clear any old answer for this key
#     if cache_key in answers:
#         del answers[cache_key]

#     # 1. Trigger Frappe Popup
#     try:
#         requests.post(
#             "http://localhost:8000/api/method/hrms.hr.page.pipal_hr_dashboard.pipal_hr_dashboard.trigger_agent_popup",
#             json={"field": field_label, "user_id": user_id, "cache_key": cache_key},
#             headers=headers,
#             timeout=5
#         )
#     except:
#         print(f"⚠️ Could not reach Frappe for {field_label}")

#     # 2. WAIT LOOP (Blocking Python execution)
#     print(f"⌛ Waiting for HR to answer: {field_label}...")
#     while cache_key not in answers:
#         time.sleep(1) # Sleep to save CPU
#     # at the end of ask_human()
#     return answers.pop(cache_key)

    # 3. Return the answer and remove from dict
#     return answers.pop(cache_key)
# def ask_human(field_label, user_id, default=""):
#     """
#     Ab ye function Terminal (input) use nahi karega.
#     Ye Frappe ko signal bhejega popup dikhane ke liye.
#     """
#     cache_key = f"req_{int(time.time())}"
    
#     # 1. Frappe ko order bhejiye (Via API)
#     # Note: Port 8000 Frappe ka hai
#     FRAPPE_URL = "http://localhost:8000/api/method/hrms.hr.page.pipal_hr_dashboard.pipal_hr_dashboard.trigger_agent_popup"
#     HEADERS = {
#         "Authorization": "token fe8e26f072ee6aa:b82f8b707e46d4c",
#         "Content-Type": "application/json"
#     }
    
#     payload = {
#         "field": field_label,
#         "user_id": user_id,
#         "cache_key": cache_key
#     }
    
#     try:
#         requests.post(FRAPPE_URL, json=payload, headers=HEADERS)
#     except Exception as e:
#         print(f"Error connecting to Frappe: {e}")
#         return default

#     # 2. WAIT: Jab tak FastAPI server mein answer na aa jaye
#     # Hum FastAPI ke 'answers' dictionary ko check karenge
#     # (Ye logic hamare agent_fastapi.py mein handle hoga)
    
#     from agent_fastapi import answers # Import the shared dict
    
#     timeout = 300 # 5 minutes
#     start_time = time.time()
    
#     while cache_key not in answers:
#         if (time.time() - start_time) > timeout:
#             return default
#         time.sleep(1)
    
#     # Answer mil gaya! Dict se nikalo aur return karo
#     return answers.pop(cache_key)

def employee_exists(user_id):
    """Check if employee already exists - prevents duplicates"""
    url = f"{FRAPPE_URL}/api/resource/Employee?filters=[[\"user_id\",\"=\",\"{user_id}\"]]"
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json().get("data", [])
        return len(data) > 0
    except:
        return False

def submit_to_frappe(data):
    """Submit employee data to Frappe"""
    url = f"{FRAPPE_URL}/api/resource/Employee"
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            emp_id = response.json().get("data", {}).get("name")
            print(f"\n✨ SUCCESS: Employee {emp_id} created!")
            return True
        else:
            print(f"\n❌ FRAPPE ERROR: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")
        return False

# === 3. CREWAI TOOLS ===

@tool("fetch_pending_users")
def fetch_pending_users() -> str:
    """Fetch all users with 'Onboarding Employee' role"""
    role_filter = json.dumps([["Has Role", "role", "=", "Onboarding Employee"]])
    user_url = f"{FRAPPE_URL}/api/resource/User?filters={role_filter}&fields=[\"name\",\"first_name\",\"middle_name\",\"last_name\",\"gender\",\"birth_date\"]"
    
    try:
        users = requests.get(user_url, headers=headers, timeout=5).json().get("data", [])
        pending = [u for u in users if u['name'] not in EXCLUDE_EMAILS]
        return json.dumps(pending[:5])  # ⚡ Limit to 5 for speed
    except Exception as e:
        print(f"Connection error: {e}")
        return json.dumps([])
    
@tool("collect_employee_details")
def collect_employee_details(
    user_name: str,
    first_name: str,
    last_name: str,
    gender: str,
    birth_date: str
) -> str:
    """Interactively collect employee details (terminal behavior, CrewAI-safe)."""

    # ------------------------------------------------------------------
    # 0. HARD SAFETY – NEVER TRUST CREWAI TOOL ARGS
    # ------------------------------------------------------------------
    user_name = str(user_name or "").strip()
    if not user_name:
        return "FAILED: Missing user_name"

    # Self-heal names (CrewAI may pass None / empty on retries)
    if not first_name:
        first_name = user_name.split("@")[0].split(".")[0].capitalize()

    if not last_name:
        parts = user_name.split("@")[0].split(".")
        last_name = parts[-1].capitalize() if len(parts) > 1 else "User"

    # Always re-derive personal email
    personal_email = user_name

    print(f"\n{'='*60}\n🚀 AGENT STARTING ONBOARDING: {user_name}\n{'='*60}")

    # ------------------------------------------------------------------
    # 1. DUPLICATE CHECK
    # ------------------------------------------------------------------
    if employee_exists(user_name):
        print(f"⏭️ Skipping {user_name}: Employee record already exists.")
        return json.dumps({"status": "skipped"})

    # ------------------------------------------------------------------
    # 2. COLLECT INPUTS (EXACT TERMINAL FLOW)
    # ------------------------------------------------------------------
    salutation = ask_human("Salutation (Mr, Ms, Mx)", user_name, "Mr")

    emp_num = ask_human("Employee ID (employee_number)", user_name)
    emp_num = "".join(filter(str.isdigit, str(emp_num or "")))
    if not emp_num:
        return "FAILED: Invalid Employee ID"

    branch = ask_human("Branch", user_name, "Pune")
    dept = ask_human("Department", user_name)
    desig = ask_human("Designation (e.g., Python Developer)", user_name)
    reports_to = ask_human("Reports To (Manager Employee ID)", user_name)

    mobile = ask_human("Mobile (10 digits)", user_name)
    mobile = str(mobile or "").strip()
    if mobile and not mobile.startswith("+"):
        mobile = f"+91{mobile}"

    company_email = ask_human(
        "Company Email",
        user_name,
        f"hr@{user_name.split('@')[-1]}"
    )

    address = ask_human("Current & Permanent Address", user_name)
    emer_name = ask_human("Emergency Contact Name", user_name)

    pan = ask_human("PAN Number", user_name)
    bank = ask_human("Bank Name", user_name)
    acc = ask_human("Bank Account No", user_name)
    ifsc = ask_human("IFSC Code", user_name)

    ctc = ask_human("CTC (Numeric)", user_name, "0")
    try:
        ctc = float(ctc)
    except:
        ctc = 0.0

    id_type = ask_human(
        "ID Type (Aadhar Card, Pan Card, Voter Id)",
        user_name,
        "Pan Card"
    )
    id_val = ask_human("ID Number", user_name)

    # ------------------------------------------------------------------
    # 3. FINAL PAYLOAD (ALL MANDATORY FIELDS GUARANTEED)
    # ------------------------------------------------------------------
    employee_json = {
        "doctype": "Employee",
        "naming_series": "EMP-.YYYY.-.#####",

        "first_name": first_name,
        "middle_name": "",
        "last_name": last_name,
        "user_id": user_name,
        "salutation": salutation,

        "gender": gender or "Male",
        "date_of_birth": birth_date or "1995-01-01",
        "status": "Active",

        "employee_number": emp_num,
        "date_of_joining": datetime.now().strftime("%Y-%m-%d"),
        "company": "mPHATEK SYSTEMS",

        "department": dept,
        "designation": desig,
        "branch": branch,
        "reports_to": reports_to if reports_to else None,

        "cell_number": mobile,
        "company_email": company_email,
        "personal_email": personal_email,
        "prefered_contact_email": "Company Email",

        "current_address": address,
        "permanent_address": address,

        "person_to_be_contacted": emer_name,
        "relation": "Relative",
        "emergency_phone_number": mobile,

        "ctc": ctc,
        "salary_currency": "INR",
        "salary_mode": "Bank",

        "bank_name": bank,
        "bank_ac_no": acc,
        "ifsc_code": ifsc,
        "pan_number": pan,
        "marital_status": "single",

        "identity_documents": [
            {
                "document_type": id_type,
                "document_number": id_val,
                "name_on_document": f"{first_name} {last_name}".strip()
            }
        ]
    }

    # ------------------------------------------------------------------
    # 4. SUBMIT (NO RETRIES ON HARD FAILURE)
    # ------------------------------------------------------------------
    print(f"📡 DEBUG: Creating employee {first_name} {last_name} ({emp_num})")

    success = submit_to_frappe(employee_json)

    if success:
        return f"SUCCESS: {first_name} created with ID {emp_num}"
    else:
        return f"FAILED: Frappe rejected Employee {emp_num}"


# @tool("collect_employee_details")
# def collect_employee_details(user_name: str, first_name: str, last_name: str, gender: str, birth_date: str) -> str:
#     """Interactively collect ALL employee details including Identity Docs and then submit to Frappe."""
    
#     # Check if already exists
#     if employee_exists(user_name):
#         return f"Skipped: {user_name} already exists."

#     print(f"🚀 Starting Sequential Collection for {first_name}")

#     # --- LINEAR DATA COLLECTION ---
#     salutation = ask_human("Salutation (Mr, Ms, Mx)", user_name, "Mr")
#     emp_id     = ask_human("Employee ID", user_name)
#     branch     = ask_human("Branch", user_name, "Pune")
#     dept       = ask_human("Department", user_name)
#     desig      = ask_human("Designation", user_name)
#     mobile     = ask_human("Mobile Number", user_name)
#     pan        = ask_human("PAN Number", user_name)
#     bank       = ask_human("Bank Name", user_name)
#     acc_no     = ask_human("Account Number", user_name)
#     ifsc       = ask_human("IFSC Code", user_name)
#     ctc        = ask_human("CTC (Numeric)", user_name, "0")
    
#     # Mandatory Identity Document Fields
#     id_type    = ask_human("ID Type (Aadhar Card, Pan Card, Voter Id)", user_name, "Pan Card")
#     id_val     = ask_human("ID Number", user_name)

#     # --- DATA CONSTRUCTION (Including Child Table) ---
#     employee_data = {
#         "doctype": "Employee",
#         "naming_series": "EMP-.YYYY.-.#####",
#         "first_name": first_name,
#         "last_name": last_name,
#         "user_id": user_name,
#         "salutation": salutation,
#         "gender": gender or "Male",
#         "date_of_birth": birth_date or "1995-01-01",
#         "employee_number": emp_id,
#         "branch": branch,
#         "department": dept,
#         "designation": desig,
#         "cell_number": mobile,
#         "pan_number": pan,
#         "bank_name": bank,
#         "bank_ac_no": acc_no,
#         "ifsc_code": ifsc,
#         "ctc": float(ctc) if ctc else 0,
#         "company": "mPHATEK SYSTEMS",
#         "status": "Active",
#         "date_of_joining": datetime.now().strftime("%Y-%m-%d"),
#         "salary_currency": "INR",
#         "salary_mode": "Bank",
#         # Adding the mandatory Identity Documents Child Table
#         "identity_documents": [
#             {
#                 "document_type": id_type,
#                 "document_number": id_val,
#                 "name_on_document": f"{first_name} {last_name}".strip()
#             }
#         ]
#     }

#     # --- SUBMIT TO FRAPPE ---
#     print(f"📡 Sending final data to Frappe for {first_name}...")
#     success = submit_to_frappe(employee_data)
    
#     if success:
#         return f"SUCCESS: Employee {first_name} has been onboarded with Identity Documents."
#     else:
#         return f"FAILED: Error saving {first_name}. Check if all mandatory fields are filled."
# @tool("collect_employee_details")
# def collect_employee_details(user_name: str, first_name: str, last_name: str, gender: str, birth_date: str) -> str:
#     """Interactively collect employee details - SAME FORMAT AS BEFORE"""
    
#     print(f"\n{'='*60}\n🚀 AGENT STARTING ONBOARDING: {user_name}\n{'='*60}")
    
#     # Check if already exists
#     if employee_exists(user_name):
#         print(f"⏭️ Skipping {user_name}: Employee record already exists.")
#         return json.dumps({"status": "skipped"})
    
#     # Collect all details (same questions as before)
#     salutation = ask_human("Salutation (Mr, Ms, Mx)", "Mr")
#     emp_num = ask_human("Employee ID (employee_number)")
#     branch = ask_human("Branch", "Pune")
#     dept = ask_human("Department")
#     desig = ask_human("Designation (e.g., Python Developer)")
#     reports_to = ask_human("Reports To (Manager Employee ID)")
#     mobile = ask_human("Mobile (10 digits)")
    
#     if mobile and not mobile.startswith('+'):
#         mobile = f"+91-{mobile}"
    
#     comp_email = ask_human("Company Email", f"hr@{user_name.split('@')[-1]}")
#     address = ask_human("Current & Permanent Address")
#     emer_name = ask_human("Emergency Contact Name")
#     pan = ask_human("PAN Number")
#     bank = ask_human("Bank Name")
#     acc = ask_human("Bank Account No")
#     ifsc = ask_human("IFSC Code")
#     ctc = ask_human("CTC (Numeric)", "0")
#     id_type = ask_human("ID Type (Aadhar Card, Pan Card, Voter Id)", "Pan Card")
#     id_val = ask_human("ID Number")
    
#     # Build JSON
#     employee_json = {
#         "doctype": "Employee",
#         "naming_series": "EMP-.YYYY.-.#####",
#         "first_name": first_name,
#         "middle_name": "",
#         "last_name": last_name,
#         "user_id": user_name,
#         "salutation": salutation,
#         "gender": gender or "Male",
#         "date_of_birth": birth_date or "1995-01-01",
#         "status": "Active",
#         "employee_number": emp_num,
#         "date_of_joining": datetime.now().strftime("%Y-%m-%d"),
#         "company": "mPHATEK SYSTEMS",
#         "department": dept,
#         "designation": desig,
#         "branch": branch,
#         "reports_to": reports_to if reports_to else None,
#         "cell_number": mobile,
#         "company_email": comp_email,
#         "personal_email": user_name,
#         "prefered_contact_email": "Company Email",
#         "current_address": address,
#         "permanent_address": address,
#         "person_to_be_contacted": emer_name,
#         "relation": "Relative",
#         "emergency_phone_number": mobile,
#         "ctc": float(ctc) if ctc else 0,
#         "salary_currency": "INR",
#         "salary_mode": "Bank",
#         "bank_name": bank,
#         "bank_ac_no": acc,
#         "ifsc_code": ifsc,
#         "pan_number": pan,
#         "marital_status": "single",
#         "identity_documents": [
#             {
#                 "document_type": id_type,
#                 "document_number": id_val,
#                 "name_on_document": f"{first_name} {last_name}".strip()
#             }
#         ]
#     }
    
#     # Confirmation before submit
#     print(f"\n--- Agent Review Complete for {first_name} ---")
#     if input("Submit to Frappe? (y/n): ").lower() == 'y':
#         success = submit_to_frappe(employee_json)
#         return json.dumps({"status": "submitted" if success else "failed"})
#     else:
#         return json.dumps({"status": "cancelled"})

# === 4. AGENT DEFINITION ===

hr_agent = Agent(
    role='HR Onboarding Specialist',
    goal='Onboard employees by collecting their details and submitting to Frappe',
    backstory="""You are an HR onboarding specialist. Your job is to:
    1. Fetch the list of users needing onboarding
    2. For each user, collect their details via interactive prompts
    3. Submit the data to Frappe
    Be efficient and clear in your communication.""",
    tools=[fetch_pending_users, collect_employee_details],
    llm=llama_llm,
    verbose=False,  # ⚡ Disable verbose for speed
    max_iter=5,  # ⚡ Limit iterations
    memory=False  # ⚡ Disable memory overhead
)

# === 5. TASK DEFINITION ===
onboarding_task = Task(
    description="""
    1. Fetch the list of pending users.
    2. For the first user, call 'collect_employee_details' ONCE with all basic info.
    3. The tool will handle all interactive questions internally. 
    4. Once the tool returns a success message, the task is finished. DO NOT call the tool again for the same user.
    """,
    expected_output="Final status of the onboarding process.",
    agent=hr_agent)
# )
# onboarding_task = Task(
#     description="""
#     1. Call fetch_pending_users to get the list of users to onboard
#     2. For EACH user in the list:
#        a. Extract: user email, first_name, last_name, gender, birth_date
#        b. Call collect_employee_details with those values
#        c. Wait for submission confirmation
#     3. After processing each user, move to the next
#     """,
#     expected_output="Confirmation of all employees successfully onboarded",
#     agent=hr_agent,
#     max_retries=1  # ⚡ Reduce retries
# )

# === 6. CREW ===

crew = Crew(
    agents=[hr_agent],
    tasks=[onboarding_task],
    verbose=False,  # ⚡ Less logging = faster
    max_iter=10 # ⚡ Global iteration limit
)

# === 7. MAIN EXECUTION ===

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 HR ONBOARDING AGENT STARTED")
    print("="*60)
    
    start_time = time.time()
    crew.kickoff()
    
    elapsed = time.time() - start_time
    print(f"\n⏱️ Total execution time: {elapsed:.2f} seconds")
    print("="*60)