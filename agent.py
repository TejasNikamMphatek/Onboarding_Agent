import os
import json
import requests
from datetime import datetime
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
import time

# === 1. CONFIGURATION ===
os.environ["OPENAI_API_KEY"] = "NA"
FRAPPE_URL = "http://localhost:8000"
API_KEY = "fe8e26f072ee6aa" 
API_SECRET = "b82f8b707e46d4c" 

EXCLUDE_EMAILS = ["hr@mphatek.com", "admin@mphatek.com", "administrator"]

# ⚡ HIGH-SPEED LLAMA3 CONFIG
llama_llm = LLM(
    model="ollama/llama3",
    base_url="http://localhost:11434",
    api_key="ollama",
    temperature=0.2,  # ⚡ Lower = faster + consistent
    top_p=0.85,  # ⚡ Reduce token generation
    top_k=40,  # ⚡ Limit choices
)

headers = {"Authorization": f"token {API_KEY}:{API_SECRET}", "Content-Type": "application/json"}

# === 2. HELPER FUNCTIONS ===

def ask_human(field_label, default=""):
    """Ask human for input - same format as before"""
    prompt = f"   Enter {field_label}"
    if default:
        prompt += f" [Default: {default}]"
    print(f"\n🤖 [AI AGENT]: {prompt}:")
    val = input("   >> ").strip()
    return val if val else default

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
def collect_employee_details(user_name: str, first_name: str, last_name: str, gender: str, birth_date: str) -> str:
    """Interactively collect employee details - SAME FORMAT AS BEFORE"""
    
    print(f"\n{'='*60}\n🚀 AGENT STARTING ONBOARDING: {user_name}\n{'='*60}")
    
    # Check if already exists
    if employee_exists(user_name):
        print(f"⏭️ Skipping {user_name}: Employee record already exists.")
        return json.dumps({"status": "skipped"})
    
    # Collect all details (same questions as before)
    salutation = ask_human("Salutation (Mr, Ms, Mx)", "Mr")
    emp_num = ask_human("Employee ID (employee_number)")
    branch = ask_human("Branch", "Pune")
    dept = ask_human("Department")
    desig = ask_human("Designation (e.g., Python Developer)")
    reports_to = ask_human("Reports To (Manager Employee ID)")
    mobile = ask_human("Mobile (10 digits)")
    
    if mobile and not mobile.startswith('+'):
        mobile = f"+91-{mobile}"
    
    comp_email = ask_human("Company Email", f"hr@{user_name.split('@')[-1]}")
    address = ask_human("Current & Permanent Address")
    emer_name = ask_human("Emergency Contact Name")
    pan = ask_human("PAN Number")
    bank = ask_human("Bank Name")
    acc = ask_human("Bank Account No")
    ifsc = ask_human("IFSC Code")
    ctc = ask_human("CTC (Numeric)", "0")
    id_type = ask_human("ID Type (Aadhar Card, Pan Card, Voter Id)", "Pan Card")
    id_val = ask_human("ID Number")
    
    # Build JSON
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
        "company_email": comp_email,
        "personal_email": user_name,
        "prefered_contact_email": "Company Email",
        "current_address": address,
        "permanent_address": address,
        "person_to_be_contacted": emer_name,
        "relation": "Relative",
        "emergency_phone_number": mobile,
        "ctc": float(ctc) if ctc else 0,
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
    
    # Confirmation before submit
    print(f"\n--- Agent Review Complete for {first_name} ---")
    if input("Submit to Frappe? (y/n): ").lower() == 'y':
        success = submit_to_frappe(employee_json)
        return json.dumps({"status": "submitted" if success else "failed"})
    else:
        return json.dumps({"status": "cancelled"})

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
    1. Call fetch_pending_users to get the list of users to onboard
    2. For EACH user in the list:
       a. Extract: user email, first_name, last_name, gender, birth_date
       b. Call collect_employee_details with those values
       c. Wait for submission confirmation
    3. After processing each user, move to the next
    """,
    expected_output="Confirmation of all employees successfully onboarded",
    agent=hr_agent,
    max_retries=1  # ⚡ Reduce retries
)

# === 6. CREW ===

crew = Crew(
    agents=[hr_agent],
    tasks=[onboarding_task],
    verbose=False,  # ⚡ Less logging = faster
    max_iter=10  # ⚡ Global iteration limit
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