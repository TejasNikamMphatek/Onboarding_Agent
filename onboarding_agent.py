import os
import json
import requests
from datetime import datetime
from crewai import Agent, Task, Crew, LLM

# === 1. CONFIGURATION ===
os.environ["OPENAI_API_KEY"] = "NA"
FRAPPE_URL = "http://localhost:8000"
API_KEY = "fe8e26f072ee6aa" 
API_SECRET = "b82f8b707e46d4c" 

# List of emails the agent should NEVER process (HR, Admin, etc.)
EXCLUDE_EMAILS = ["hr@mphatek.com", "admin@mphatek.com", "administrator"]

llama_llm = LLM(model="ollama/llama3", base_url="http://localhost:11434", api_key="ollama")
headers = {"Authorization": f"token {API_KEY}:{API_SECRET}", "Content-Type": "application/json"}

# --- HELPER: Terminal Interaction ---
def ask_human(field_label, default=""):
    prompt = f"   Enter {field_label}"
    if default:
        prompt += f" [Default: {default}]"
    print(f"\n🤖 [AI AGENT]: {prompt}:")
    val = input("   >> ").strip()
    return val if val else default

# --- API: Check for Existing Employee ---
def employee_exists(user_id):
    """Agent checks the environment to prevent duplicate work"""
    url = f"{FRAPPE_URL}/api/resource/Employee?filters=[[\"user_id\",\"=\",\"{user_id}\"]]"
    response = requests.get(url, headers=headers)
    data = response.json().get("data", [])
    return len(data) > 0

# --- API: Submit to Frappe ---
def submit_to_frappe(data):
    url = f"{FRAPPE_URL}/api/resource/Employee"
    try:
        response = requests.post(url, headers=headers, json=data)
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

# --- MAIN LOGIC ---
def run_onboarding_crew():
    # Fetching users with "Onboarding Employee" role
    role_filter = json.dumps([["Has Role", "role", "=", "Onboarding Employee"]])
    user_url = f"{FRAPPE_URL}/api/resource/User?filters={role_filter}&fields=[\"name\",\"first_name\",\"middle_name\",\"last_name\",\"gender\",\"birth_date\"]"
    
    try:
        users = requests.get(user_url, headers=headers).json().get("data", [])
    except:
        print("Could not connect to Frappe. Check if bench is running.")
        return

    # Filter out excluded emails
    pending_users = [u for u in users if u['name'] not in EXCLUDE_EMAILS]

    if not pending_users:
        print("\n✅ Agent Report: No new users to onboard (All excluded or none found).")
        return

    for user in pending_users:
        print(f"\n{'='*60}\n🚀 AGENT STARTING ONBOARDING: {user['name']}\n{'='*60}")

        # SMART CHECK: Skip if already an employee
        if employee_exists(user['name']):
            print(f"⏭️ Skipping {user['name']}: Employee record already exists.")
            continue

        # --- DATA GATHERING ---
        salutation = ask_human("Salutation (Mr, Ms, Mx)", "Mr")
        emp_num = ask_human("Employee ID (employee_number)")
        branch = ask_human("Branch", "Pune")
        dept = ask_human("Department")
        desig = ask_human("Designation (e.g., Python Developer)")
        reports_to = ask_human("Reports To (Manager Employee ID)")
        mobile = ask_human("Mobile (10 digits)")
        if not mobile.startswith('+'): mobile = f"+91-{mobile}"
        comp_email = ask_human("Company Email", f"hr@{user['name'].split('@')[-1]}")
        address = ask_human("Current & Permanent Address")
        emer_name = ask_human("Emergency Contact Name")
        pan = ask_human("PAN Number")
        bank = ask_human("Bank Name")
        acc = ask_human("Bank Account No")
        ifsc = ask_human("IFSC Code")
        ctc = ask_human("CTC (Numeric)", "0")
        id_type = ask_human("ID Type (Aadhar Card, Pan Card, Voter Id)", "Pan Card")
        id_val = ask_human("ID Number")

        # Building JSON strictly following your employee.json schema
        employee_json = {
            "doctype": "Employee",
            "naming_series": "EMP-.YYYY.-.#####",
            "first_name": user.get('first_name'),
            "middle_name": user.get('middle_name'),
            "last_name": user.get('last_name'),
            "user_id": user['name'],
            "salutation": salutation,
            "gender": user.get('gender') or "Male",
            "date_of_birth": user.get('birth_date') or "1995-01-01",
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
            "personal_email": user['name'],
            "prefered_contact_email": "Company Email",
            "current_address": address,
            "permanent_address": address,
            "person_to_be_contacted": emer_name,
            "relation": "Relative",
            "emergency_phone_number": mobile,
            "ctc": float(ctc),
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
                    "name_on_document": f"{user['first_name']} {user.get('last_name') or ''}".strip()
                }
            ]
        }

        print(f"\n--- Agent Review Complete for {user['first_name']} ---")
        if input("Submit to Frappe? (y/n): ").lower() == 'y':
            submit_to_frappe(employee_json)

if __name__ == "__main__":
    run_onboarding_crew()