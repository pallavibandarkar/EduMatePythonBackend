from flask import Flask, request, jsonify
from flask_cors import CORS 
import json
# Import your existing functions here
#from your_grading_module import process_document  

from grading import process_document

app = Flask(__name__)

@app.route('/grade', methods=['POST'])
def grade():
    data = request.json
    file_url = data.get('file_url')

    if not file_url:
        return jsonify({'error': 'File URL is required'}), 400

    result = process_document(file_url)

    if result['success']:
        return jsonify(result['results']), 200
    else:
        return jsonify({'error': result['error']}), 500

if __name__ == '__main__':
    app.run(port=5001)  