# ==================== IMPORTS ====================
import asyncio
from requests.exceptions import HTTPError
from mlflow.gateway import set_gateway_uri, query
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
 
# ==================== CONSTANTS AND CONFIGURATION ====================
#specify model here  
ROUTE = 'chat-gpt-35-turbo-16k'  # Updated route to 'chat' endpoint
TEMPERATURE = 0.0
BASE_DELAY = 5
EST = timezone(timedelta(hours=-5))
 
INSTRUCTIONS = "Your role is a clinical scribe whose job it is to extract clinical 
information from a patient note so a clinician can appropriately and comprehensively 
asses the patient's health. For the clinical note provided, produce a structured 
table only consisting of only all symptoms and diagnoses mentioned. In this table, 
in column 1, list the section of the note the symptom or diagnosis is listed in; 
in column 2 list each symptom or diagnosis within each section of the provided 
clinical note; in column 3 list the corresponding CUI for each symptom or diagnosis; 
in column 4 list the status of the symptom or diagnosis as being current or past or 
future if the clinician writes they think it may develop in the future; in column 5 
list the clinician’s interpretation of whether the diagnosis is ruled-out, likely, 
unlikely, is a confirmed-diagnosis, was previously-diagnosed, or is a side effect 
of a procedure or medication; in column 6 list the procedure or medication it may 
be a side effect of; in column 7 list the person associated with the symptom or 
diagnosis. Exclude mention of clinical labs, surgical interventions and procedures, 
medications, and physical exam test results in column 2 of this table and only include symptoms and diagnoses."

# ==================== HELPER FUNCTIONS ====================
 
def format_response(text, response):
    return {
        'timestamp': datetime.today().astimezone(EST).replace(tzinfo=None),
        'model': response.get("metadata").get("model"),
        'temperature': TEMPERATURE,
        'prompt': text,
        'response': response.get("candidates")[0].get("message").get("content")
    }
 
async def async_query_with_retries(route, text, max_retries=1):
    loop = asyncio.get_event_loop()
    curr_msgs = [{'role': 'system', 'content': INSTRUCTIONS}, {'role': 'user', 'content': text}]
    for attempt in range(max_retries):
        try:
            response_data = await loop.run_in_executor(None, query, route, {"messages": curr_msgs, "temperature": TEMPERATURE})
            return format_response(text, response_data)
        except HTTPError:
            if attempt < max_retries - 1:
                await asyncio.sleep(BASE_DELAY * (2 ** attempt))
            else: # can remove to skip broken notes
                print(text)
                print("---\n")
                return {
                    'timestamp': datetime.today().astimezone(EST).replace(tzinfo=None),
                    'model': "",
                    'temperature': TEMPERATURE,
                    'prompt': text,
                    'response': ""
                }
 
async def process_prompts(prompts, route):
    return await asyncio.gather(*[async_query_with_retries(route, text) for text in prompts])
 
def execute_async_tasks():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    prompts = [row["text"] for row in df]
    return loop.run_until_complete(process_prompts(prompts, ROUTE))
 
# ==================== MAIN EXECUTION ====================
#specify spark notes table here
df = spark.table("notes_data").select("text").limit(5).collect()

with ThreadPoolExecutor(max_workers=10) as executor:
    prompt_response = executor.submit(execute_async_tasks).result()
 
prompt_response_df = spark.createDataFrame(prompt_response)
display(prompt_response_df)
