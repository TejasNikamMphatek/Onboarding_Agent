import os
import json
import requests
from crewai import Agent, Task, Crew, LLM

# === 1. BYPASS ALL EXTERNAL CHECKS ===
os.environ["OPENAI_API_KEY"] = "NA"
os.environ["OPENAI_MODEL_NAME"] = "ollama/llama3" # Sets a default to prevent internal errors

# === 2. CONFIGURATION ===
FRAPPE_URL = "http://localhost:8000"
API_KEY = "fe8e26f072ee6aa"
API_SECRET = "b82f8b707e46d4c"

# Initialize Local Llama 3 Brain correctly
llama_llm = LLM(
    model="ollama/llama3",
    base_url="http://localhost:11434",
    api_key="ollama" # Using 'ollama' as the key is the magic fix
)

headers = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json"
}

# === 3. TOOLS ===

def get_onboarding_users():
    # Improved filter to catch the role in the child table
    role_filter = json.dumps([["Has Role", "role", "=", "Onboarding Employee"]])
    url = f"{FRAPPE_URL}/api/resource/User?filters={role_filter}&fields=[\"name\",\"full_name\",\"bio\"]"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []
# === 4. THE SCOUT AGENT ===
scout = Agent(
    role='HR Scout',
    goal='Identify users with a complete bio for onboarding.',
    backstory='You are a helpful HR assistant at Mphatek.',
    llm=llama_llm,
    memory=False, # DISABLING MEMORY is crucial to avoid OpenAI embedding errors
    verbose=True,
    allow_delegation=False
)

def run_onboarding_crew():
    users = get_onboarding_users()
    if not users:
        print("No users found in onboarding status.")
        return

    scout_task = Task(
        description=f"Analyze these users: {json.dumps(users)}. List who has a bio and who doesn't.",
        expected_output="A clean list of 'Ready' and 'Pending' users.",
        agent=scout
    )

    crew = Crew(
        agents=[scout], 
        tasks=[scout_task], 
        verbose=True,
        memory=False # Must be False here too
    )

    print("\n### Crew is thinking... ###\n")
    result = crew.kickoff()
    print(f"\n### Scout Report ###\n{result}")

if __name__ == "__main__":
    run_onboarding_crew()