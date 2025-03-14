import json
import requests
import os
import tempfile
from google import genai
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Tuple, TypedDict, Union

class PaperCheckResult(BaseModel):
    Name: str = Field("", description="Paper taker's name or anything that hels identify the paper taker")
    marks: int
    remarks: List[str]
    suggestions: List[str]
    errors: List[str]

class ProcessResult(TypedDict):
    success: bool
    error: str | None
    results: List[Dict[str, Any]] | None

def download_from_url(url: str) -> Tuple[str, str]:
    """
    Downloads a file from a URL to a temporary file
    Returns: Tuple of (temp_file_path, filename)
    """
    try:
        # Get filename from URL
        filename = url.split("/")[-1]
        
        # Download the file to a temporary location
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses
        
        # Create temporary file with appropriate extension
        file_ext = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_path = temp_file.name
        
        return temp_path, filename
    except Exception as e:
        raise Exception(f"Error downloading file: {str(e)}")

def prepare_document(file_path: str) -> Dict[str, Any]:
    """
    Prepares the document and gets initial response
    Returns: Dictionary with raw response
    """
    try:
        # Initialize the Google AI client
        client = genai.Client(api_key="AIzaSyD4lR1WQ1yaZumSFtMVTG_0Y8d0oRy1XhA")
        
        # Upload the file
        uploaded_file = client.files.upload(file=file_path)
        
        # First prompt for general analysis
        initial_prompt = """
        Analyze this academic paper and provide feedback. Include:
        1. Overall quality score (0-100)
        2. Positive aspects of the paper
        3. Areas that need improvement
        4. Any errors or problems found
        """
        
        # Get initial response
        initial_response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[uploaded_file, initial_prompt]
        )
        
        return {
            "success": True, 
            "uploaded_file": uploaded_file,
            "initial_response": initial_response.text
        }
        
    except Exception as e:
        return {"success": False, "error": f"Error preparing document: {str(e)}"}

def analyze_document(initial_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes initial response and converts it to structured format
    Returns: Dictionary with structured results
    """
    try:
        if not initial_result["success"]:
            return initial_result
            
        client = genai.Client(api_key="AIzaSyD4lR1WQ1yaZumSFtMVTG_0Y8d0oRy1XhA")
        
        structure_prompt = f"""
        Convert the following feedback into a structured JSON format:

        {initial_result['initial_response']}

        The JSON should have this structure:
        {{  "Name": "Roll No or name of the paper taker if found, otherwise empty string",
            "marks": integer (0-100) it should depend on how good remarks are and how many errors there are,
            "remarks": [list of positive comments],
            "suggestions": [list of improvement areas],
            "errors": [list of problems found]
        }}

        IMPORTANT: Ensure marks is a valid integer between 0 and 100. If no specific score is found, use 0.
        Ensure all arrays are empty lists [] instead of null when there are no items.
        Ensure Name is an empty string "" if no name is found.
        """
        
        # Get structured response
        structured_response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=structure_prompt,
            config={
                'response_mime_type': 'application/json'
            }
        )

        # Parse the response safely
        try:
            # Clean the response text to ensure it's valid JSON
            response_text = structured_response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            data = json.loads(response_text)
            
            # Ensure data structure is correct and all fields are valid
            if isinstance(data, dict):
                data["marks"] = int(data.get("marks", 0))  # Convert to int, default to 0
                data["Name"] = str(data.get("Name", ""))  # Convert to string, default to empty string
                data["remarks"] = list(data.get("remarks", []))
                data["suggestions"] = list(data.get("suggestions", []))
                data["errors"] = list(data.get("errors", []))
            
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse AI response: {str(e)}"}
        except (ValueError, TypeError) as e:
            return {"success": False, "error": f"Invalid value conversion: {str(e)}"}
        
        if not isinstance(data, list):
            data = [data]
            
        results = [PaperCheckResult(**item) for item in data]
        final_results = {"success": True, "results": [r.model_dump() for r in results]}
        return final_results
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def process_document(file_path_or_url: str) -> ProcessResult:
    """
    Main function that coordinates the document processing
    Accepts either a local file path or a URL
    """
    temp_file = None
    try:
        # Check if the input is a URL
        if file_path_or_url.startswith(('http://', 'https://')):
            # Download the file from URL
            temp_file, filename = download_from_url(file_path_or_url)
            file_path = temp_file
        else:
            # Use the provisde file path directly
            file_path = file_path_or_url
        
        # First get raw analysis
        initial_result = prepare_document(file_path)
        if not initial_result["success"]:
            return {"success": False, "error": initial_result["error"], "results": None}
            
        # Then convert to structured format
        result = analyze_document(initial_result)
        if not result["success"]:
            return {"success": False, "error": result["error"], "results": None}
            
        return {"success": True, "error": None, "results": result["results"]}
        
    except Exception as e:
        return {"success": False, "error": str(e), "results": None}
    finally:
        # Clean up temporary file if it was created
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

if __name__ == "__main__":
    # Example file URL from Cloudinary
    file_url = "https://res.cloudinary.com/dvqkoleje/image/upload/v1741875116/EduMate/fcrikg6o5twe58iyqo7v.pdf"
    result = process_document(file_url)
    
    if result["success"]:
        for paper_result in result["results"]:
            print(f"Name: {paper_result['Name']}")
            print(f"Marks: {paper_result['marks']}")
            print(f"Remarks: {paper_result['remarks']}")
            print(f"Suggestions: {paper_result['suggestions']}")
            print(f"Errors: {paper_result['errors']}")
            print("-" * 50)
    else:
        print("Error:", result["error"])