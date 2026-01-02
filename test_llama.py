from langchain_ollama import OllamaLLM

# Initialize your local model
try:
    # This uses the new recommended class
    model = OllamaLLM(model="llama3")
    
    print("Sending message to Llama...")
    response = model.invoke("Hello! You are an HR Assistant for Mphatek. Are you ready to help with employee onboarding?")
    
    print("\n--- Llama's Response ---")
    print(response)
    print("------------------------")
except Exception as e:
    print(f"Error: {e}")
