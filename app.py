from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__, static_folder='public', static_url_path='/public')
CORS(app)

GOOGLE_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbx90ShJ2m4mPLtZ3J0iwcbvGLs0rPgF_gNtbmbeZRz5gVnQASt4NVs8J1fmajJgqhY0/exec'
ZAPIER_URL = 'https://hooks.zapier.com/hooks/catch/22674586/2p4akpm/'

# SEC API URL and Key
API_KEY = os.getenv('API_KEY', '688a3e6deb6d81230af2505d8cea11309e2e76665bc27029cd10e4648671467b')
API_URL = 'https://api.sec-api.io/form-adv/individual'

RECAPTCHA_SECRET_KEY = "6Le7Tt8qAAAAAL9pgWPC-OdH9KhQthXdMyXJRZ0t"

# Serve the static index.html file for the root route
# @app.route('/')
# def index():
#     return send_from_directory(app.static_folder, 'index.html')

# Proxy route for SEC API
@app.route('/api/search', methods=['POST'])
def search_advisor():
    data = request.json
    print("Incoming Search Data:", data)  # Log the incoming data
    query = data.get('query')
    size = data.get('size', 50)

    try:
        headers = {
            'Authorization': API_KEY,
            'Content-Type': 'application/json',
        }
        response = requests.post(API_URL, json={'query': query, 'size': size}, headers=headers)
        print("Response sent:", response)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return jsonify(response.json())  # Forward the response to the frontend
    except requests.exceptions.RequestException as e:
        print(f"Error with SEC API request: {e}")
        return jsonify({'error': 'An error occurred while processing your request.'}), 500

# Route for form submission
@app.route('/submit-form', methods=['POST'])
def submit_form():
    try:
        # Get the form data from the request
        data = request.json
        print("Form Data Received:", data)

        # Validate required fields
        required_fields = ['firstName', 'lastName', 'phone', 'email', 'isFiduciary']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            error_message = f"Missing required fields: {', '.join(missing_fields)}"
            print("Validation Error:", error_message)
            return jsonify({'status': 'error', 'message': error_message}), 400

        # Ensure "isFiduciary" is a boolean and true
        if not isinstance(data.get('isFiduciary'), bool) or not data['isFiduciary']:
            error_message = "User must confirm they are a fiduciary."
            print("Validation Error:", error_message)
            return jsonify({'status': 'error', 'message': error_message}), 400

        # Extract and flatten deviceInfo and UTM data
        device_info = data.get('deviceInfo', {})
        utm_data = data.get('utmData', {})

        # Prepare flattened data for Google Sheets
        form_data = {
            "firstName": data.get("firstName"),
            "lastName": data.get("lastName"),
            "firmName": data.get("firmName"),
            "crdNumber": data.get("crdNumber"),
            "phone": data.get("phone"),
            "email": data.get("email"),
            "isFiduciary": data.get("isFiduciary"),
            "deviceType": device_info.get("deviceType", "Unknown"),
            "browser": device_info.get("browser", "Unknown"),
            "browserLanguage": device_info.get("browserLanguage", "Unknown"),
            "utm_source": utm_data.get("utm_source", "N/A"),
            "utm_medium": utm_data.get("utm_medium", "N/A"),
            "utm_campaign": utm_data.get("utm_campaign", "N/A"),
            "utm_term": utm_data.get("utm_term", "N/A"),
            "utm_content": utm_data.get("utm_content", "N/A")
        }

        # Send the data to Google Apps Script
        response = requests.post(GOOGLE_SCRIPT_URL, json=form_data)
        response.raise_for_status()  # Raise an error for bad responses

        # Forward the response from Google Apps Script
        script_response = response.json()
        print("Google Script Response:", script_response)


        payload = {
         "lead": form_data
        }

        print('zapier request', payload)
        zap_response = requests.post(ZAPIER_URL, json=payload)
        zapier_response = zap_response.json()
        print("Zapier Response:", zapier_response)

        return jsonify({'status': 'success', 'message': 'Success.'}), 200

    except requests.exceptions.RequestException as e:
        # Log and return a more descriptive error message for HTTP errors
        print("HTTP Error:", str(e))
        return jsonify({'status': 'error', 'message': 'Failed to submit the form.'}), 500

    except Exception as e:
        # Log and return a more descriptive error message for unexpected errors
        print("Unexpected Error:", str(e))
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred.'}), 500



@app.route('/submit-form-recaptcha', methods=['POST'])
def submit_form_recaptcha():
    try:
        # Get the form data from the request
        data = request.json
        recaptcha_token = data.get("recaptchaToken")

        print("Form Data Received:", data)
        print("Recaptcha token received:", recaptcha_token)

        # Validate required fields
        required_fields = ['firstName', 'lastName', 'phone', 'email', 'isFiduciary']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            error_message = f"Missing required fields: {', '.join(missing_fields)}"
            print("Validation Error:", error_message)
            return jsonify({'status': 'error', 'message': error_message}), 400

        # Ensure "isFiduciary" is a boolean and true
        if not isinstance(data.get('isFiduciary'), bool) or not data['isFiduciary']:
            error_message = "User must confirm they are a fiduciary."
            print("Validation Error:", error_message)
            return jsonify({'status': 'error', 'message': error_message}), 400

        # Step 1: Verify reCAPTCHA token with Google
        recaptcha_response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": recaptcha_token
            }
        )
        recaptcha_result = recaptcha_response.json()
        recaptcha_score = recaptcha_result.get("score", 0)

        print("reCAPTCHA Verification Response:", recaptcha_result)

        # Step 2: Check reCAPTCHA verification result
        if not recaptcha_result.get("success") or recaptcha_score < 0.5:
            print("reCAPTCHA failed, blocking submission")
            return jsonify({
                "status": "error",
                "message": "Failed reCAPTCHA verification. You may be a bot.",
                "recaptcha_score": recaptcha_score
            }), 400

        # Extract and flatten deviceInfo and UTM data
        device_info = data.get('deviceInfo', {})
        utm_data = data.get('utmData', {})

        # Step 3: Prepare flattened data for Google Sheets
        form_data = {
            "firstName": data.get("firstName"),
            "lastName": data.get("lastName"),
            "firmName": data.get("firmName"),
            "crdNumber": data.get("crdNumber"),
            "phone": data.get("phone"),
            "email": data.get("email"),
            "isFiduciary": data.get("isFiduciary"),
            "deviceType": device_info.get("deviceType", "Unknown"),
            "browser": device_info.get("browser", "Unknown"),
            "browserLanguage": device_info.get("browserLanguage", "Unknown"),
            "utm_source": utm_data.get("utm_source") if utm_data.get("utm_source") else None,  # Preserve None
            "utm_medium": utm_data.get("utm_medium") if utm_data.get("utm_medium") else None,  # Preserve None
            "utm_campaign": utm_data.get("utm_campaign") if utm_data.get("utm_campaign") else None,  # Preserve None
            "utm_term": utm_data.get("utm_term") if utm_data.get("utm_term") else None,  # Preserve None
            "utm_content": utm_data.get("utm_content") if utm_data.get("utm_content") else None,  # Preserve None
            "reCAPTCHA_Score": recaptcha_score
        }

        print("Prepared Form Data for Google Sheets:", form_data)

        # Step 4: Send the data to Google Apps Script
        response = requests.post(GOOGLE_SCRIPT_URL, json=form_data)
        response.raise_for_status()  # Raise an error for bad responses

        # Step 5: Forward the response from Google Apps Script
        script_response = response.json()
        print("Google Script Response:", script_response)

        return jsonify(script_response)

    except requests.exceptions.RequestException as e:
        # Log and return a more descriptive error message for HTTP errors
        print("HTTP Error:", str(e))
        return jsonify({'status': 'error', 'message': 'Failed to submit the form to Google Sheets.'}), 500

    except Exception as e:
        # Log and return a more descriptive error message for unexpected errors
        print("Unexpected Error:", str(e))
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred.'}), 500


@app.route('/cp.html')
def cp_page():
    return send_from_directory(app.static_folder, 'cp.html')

@app.route('/recaptcha.html')
def recaptcha_page():
    return send_from_directory(app.static_folder, 'recaptcha.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
