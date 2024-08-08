from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
import requests
import openai
import time
import shutil
from requests.exceptions import RequestException

def create_app():
    app = Flask(__name__)

    @app.route("/")
    def transcribe_summarize():
        return render_template("sumscribe.html")
    
    @app.route("/query_ticket")
    def query_ticket():
        return render_template("query.html")
    
    @app.route("/sumscribe", methods=["POST"])
    def sumscribe():
        os.makedirs('recordings')
        os.makedirs('transcriptions')
        client = openai.OpenAI(api_key=os.getenv("C_TOKEN"))
        ticket_id = request.form['ticketID']
        load_dotenv()
        subdomain = os.getenv('SUBDOMAIN')
        search_url = f'https://{subdomain}.zendesk.com/api/v2/search.json'
        params = {'query': f'type:ticket {ticket_id}'}
        search_response = requests.get(search_url, params=params, auth=(os.getenv('Z_EMAIL'), os.getenv('Z_TOKEN')))
        data = search_response.json()
        ticket = data['results'][0]
        comments_url = f'https://{subdomain}.zendesk.com/api/v2/tickets/{ticket["id"]}/comments.json'
        comments_response = requests.get(comments_url, auth=(os.getenv('Z_EMAIL'), os.getenv('Z_TOKEN')))
        if comments_response.status_code == 200:
            comments_data = comments_response.json()
            for comment in comments_data['comments']:
                if comment['author_id'] == 403212571512:
                    shutil.rmtree('transcriptions')
                    shutil.rmtree('recordings')
                    return render_template('sumscribe.html', error='This ticket has already been transcribed and summarized.')
            for comment in comments_data['comments']:
                recording_url = comment.get('data', {}).get('recording_url')
                if recording_url:
                    break
            try:
                recording_response = requests.get(recording_url, auth=(os.getenv('Z_EMAIL'), os.getenv('Z_TOKEN')), stream=True)
                if recording_response.status_code == 200:
                    file_path = f'recordings/recording.mp3'
                    with open(file_path, 'wb') as f:
                        for chunk in recording_response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print(f"Downloaded: {file_path}")
                else:
                    error = f"Failed to download ticket, status code: {recording_response.status_code}"
                    shutil.rmtree('transcriptions')
                    shutil.rmtree('recordings')
                    return render_template('sumscribe.html', error=error)
            except Exception as e:
                error = f"Error downloading ticket: {e}"
                shutil.rmtree('transcriptions')
                shutil.rmtree('recordings')
                return render_template('sumscribe.html', error=error)
            
            txt_fp = f'transcriptions/transcription_{ticket_id}.txt'
            with open(file_path, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=f
                )
            with open(txt_fp, "w") as t:
                t.write(transcription.text)
            info = {'customer': '', 'agent': ''}
            info['customer'] = comment.get('via', {}).get('source', {}).get('from', {}).get('name')
            if info['customer'] == 'Brooklyn Low Voltage Supply':
                info['customer'] = comment.get('via', {}).get('source', {}).get('to', {}).get('name')
            info['agent'] = comment.get('data', {}).get('answered_by_name')
            messages_summary = [
                {'role': 'system', 'content': 'You are an intelligent assistant.'},
                {'role': 'user', 'content': 
                f'Summarize the issue faced by customer {info["customer"]} and how agent {info["agent"]} addressed it. Include the name of the customer\'s company if mentioned.' + 
                f'Then, if the issue was resolved, say "This issue was resolved.", otherwise say "This issue was not resolved." ' +
                f'Use no more than 150 words. Transcript: {transcription.text}'}
            ]
            for attempt in range(3):
                try:
                    chat = client.chat.completions.create(messages=messages_summary, model="gpt-4o")
                    summary = chat.choices[0].message.content
                    break
                except (openai.InternalServerError, RequestException) as e:
                    if attempt < 2:
                        wait_time = 3 ** (attempt + 1)
                        time.sleep(wait_time)
                    else:
                        error = "Something went wrong with OpenAI...please try again later."
                        shutil.rmtree('transcriptions')
                        shutil.rmtree('recordings')
                        return render_template('sumscribe.html', error=error)
                except Exception as e:
                    error = f"Error processing {file_path}: {e}"
                    shutil.rmtree('transcriptions')
                    shutil.rmtree('recordings')
                    return render_template('sumscribe.html', error=error)
            attachment_url = f'https://{subdomain}.zendesk.com/api/v2/uploads.json'
            with open(txt_fp, 'rb') as f:
                response = requests.post(
                    attachment_url, params={'filename': f'transcription_{ticket_id}'}, 
                    data=f, headers={'Content-Type': 'text/plain'}, 
                    auth=(os.getenv('Z_EMAIL'), os.getenv('Z_TOKEN'))
                )
            upload_token = response.json()['upload']['token']
            ticket_url = f'https://{subdomain}.zendesk.com/api/v2/tickets/{ticket_id}'
            note = {
                'ticket': {
                    'comment': {
                        'body': summary, 
                        'public': False, 
                        'uploads': [upload_token]
                    }
                }
            }
            requests.request("PUT", ticket_url, auth=(os.getenv('Z_EMAIL'), os.getenv('Z_TOKEN')), headers={'Content-Type': 'application/json'}, json=note)
            shutil.rmtree('transcriptions')
            shutil.rmtree('recordings')
                          
            return render_template("sumscribe.html", summary=summary)
    
    @app.route("/query", methods=["POST"])
    def query():
        client = openai.OpenAI(api_key=os.getenv("C_TOKEN"))
        ticket_id = request.form['ticketID']
        query = request.form['messageID']
        subdomain = os.getenv('SUBDOMAIN')
        comments_url = f'https://{subdomain}.zendesk.com/api/v2/tickets/{ticket_id}/comments.json'
        comments_response = requests.get(comments_url, auth=(os.getenv('Z_EMAIL'), os.getenv('Z_TOKEN')))
        if comments_response.status_code == 200:
            comments_data = comments_response.json()['comments']
            for c in comments_data:
                if c['author_id'] == 403212571512:
                    comment = c
                    break
            else:
                return render_template('query.html', error='This ticket has not been processed yet. Would you like to transcribe and summarize it?')
            summary = comment['body']
            try:
                url = comment['attachments'][0]['content_url'] 
                response = requests.get(url)
                if response.status_code == 200:
                    transcription = response.text
                else:
                    error = f"Failed to retrieve the file. Status code: {response.status_code}"
                    return render_template('query.html', error=error)
            except requests.exceptions.RequestException:
                error = f"An error has occurred. Please try again later."
                return render_template('query.html', error=error)
        else: 
            return render_template('query.html', error="Ticket could not be found.")
        messages = [
            {'role': 'system', 'content': 'You are an intelligent assistant.'},
            {'role': 'user', 'content': 
            f'{query}. Answer this question/command using proper html formatting using the following: \nCall summary: {summary}\n Transcription of call: {transcription}'}
        ]
        for attempt in range(3):
            try:
                chat = client.chat.completions.create(messages=messages, model="gpt-4o")
                answer = chat.choices[0].message.content
                break  
            except (openai.InternalServerError, RequestException):
                if attempt < 2:
                    wait_time = 3 ** (attempt + 1)
                    time.sleep(wait_time)
                else:
                    error = f"Something went wrong with OpenAI...please try again later."
                    return render_template('query.html', error=error)
        
        return render_template('query.html', answer=answer)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)


# Keep transcription and summary functionality and send to Zendesk if there is not a summary/transcription already in the ticket
# Include submit button for the transcription/summary in case user doesn't want it submitted to zendesk
# If transcription and summary already exist in ticket, allow user to prompt like ChatGPT on the transcription
# Access and print just the transcription/summary?