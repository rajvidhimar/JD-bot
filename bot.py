#!/usr/bin/env python3
"""
JD Bot - A versatile bot for various tasks
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
import re
import json
import threading
import queue
import asyncio
import concurrent.futures
from functools import partial

# Load environment variables
load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize Flask
app = Flask(__name__)

# Initialize the model with optimized settings
generation_config = {
    "temperature": 0.9,  # Increased for more creative responses
    "top_p": 0.8,
    "top_k": 40,
    "candidate_count": 1,
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# List available models
print("Available models:")
for m in genai.list_models():
    print(m.name)

model = genai.GenerativeModel(
    model_name='models/gemini-1.5-flash',
    generation_config=generation_config,
    safety_settings=safety_settings
)

# Initialize chat
chat = model.start_chat(history=[])

# Global variables to store conversation state and job details
conversation_state = {
    'role': None,
    'company': None,
    'location': None,
    'experience_required': None,
    'skills_required': None,
    'job_type': None,  # full-time, part-time, contract, etc.
    'final_job_posting': None,
    'is_generating': False,
    'generation_result': None,
    'last_action': None,  # To track the last action/question asked
    'has_asked_for_info': False,
    'partial_info': None
}

# Queue for job posting generation
job_posting_queue = queue.Queue()

# Global variables
job_details = {
    'role': None,
    'company': None,
    'location': {
        'city': None,
        'state': None,
        'country': None
    },
    'total_experience': None,
    'relevant_experience': None,
    'skills': [],
    'tech_stack': [],
    'requirements': [],
    'education': None
}

final_job_posting = None
conversation_history = []

def run_async(func):
    """Decorator to run async functions in sync context"""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(func(*args, **kwargs))
        loop.close()
        return result
    return wrapper

async def extract_job_info_async(message):
    """Async version of extract_job_info with improved extraction"""
    print(f"Starting job info extraction for message: {message}")
    
    message = message.replace('\r\n', '\n').replace('\r', '\n').replace('\\n', '\n')
    
    try:
        # Enhanced prompt for better extraction
        extraction_prompt = f"""
        Extract ALL job-related information from this message: "{message}"
        
        Rules:
        1. For role:
           - Normalize common terms (e.g., "dev" → "Developer", "BE" → "Backend")
           - Look for role-related words (engineer, developer, manager, etc.)
           - Consider context and industry standards
        
        2. For company:
           - Clean up company names (e.g., "fb" → "Facebook", "goog" → "Google")
           - Look for company indicators (at, for, with, @)
           - Consider known company names and abbreviations
        
        3. For experience:
           - Look for years of experience mentioned (e.g., "15+ years", "minimum 5 years")
           - Consider variations like "experienced", "senior", "veteran"
           - Extract both minimum and preferred years if mentioned
        
        4. For location:
           - Look for city, state, or country names
           - Consider remote/hybrid/onsite mentions
           - Default to null if not mentioned
        
        5. For skills/requirements:
           - Extract any mentioned technical skills
           - Look for soft skills or qualifications
           - Note any specific requirements
        
        Return JSON:
        {{
            "role": {{"value": "extracted role", "confidence": 0.0-1.0}},
            "company": {{"value": "extracted company", "confidence": 0.0-1.0}},
            "experience": {{"value": "extracted experience", "confidence": 0.0-1.0}},
            "location": {{"value": "extracted location", "confidence": 0.0-1.0}},
            "requirements": {{"value": ["requirement1", "requirement2"], "confidence": 0.0-1.0}}
        }}
        """
        
        response = await asyncio.to_thread(model.generate_content, extraction_prompt)
        response_text = response.text
        
        try:
            json_str = response_text.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:]
            if json_str.endswith('```'):
                json_str = json_str[:-3]
            json_str = json_str.strip()
            
            extracted_info = json.loads(json_str)
            print("Extracted info:", extracted_info)
            return extracted_info
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            return {
                "role": {"value": None, "confidence": 0.0},
                "company": {"value": None, "confidence": 0.0},
                "experience": {"value": None, "confidence": 0.0},
                "location": {"value": None, "confidence": 0.0},
                "requirements": {"value": [], "confidence": 0.0}
            }
            
    except Exception as e:
        print(f"Error in extract_job_info: {str(e)}")
        return {
            "role": {"value": None, "confidence": 0.0},
            "company": {"value": None, "confidence": 0.0},
            "experience": {"value": None, "confidence": 0.0},
            "location": {"value": None, "confidence": 0.0},
            "requirements": {"value": [], "confidence": 0.0}
        }

def extract_location(text):
    """Extract city, state, and country from location text"""
    prompt = f"""
    Extract the city, state, and country from the following text. If any is not present, return None for that field.
    Text: {text}
    Return in format: city|||state|||country
    """
    response = model.generate_content(prompt)
    parts = response.text.split('|||')
    if len(parts) == 3:
        return {
            'city': parts[0].strip() if parts[0].strip().lower() != 'none' else None,
            'state': parts[1].strip() if parts[1].strip().lower() != 'none' else None,
            'country': parts[2].strip() if parts[2].strip().lower() != 'none' else None
        }
    return {'city': None, 'state': None, 'country': None}

def extract_additional_details(text):
    """Extract additional job details using AI"""
    prompt = f"""
    Extract the following details from the text (return None if not found):
    1. Total years of experience
        - Look for patterns like "X years", "X+ years", "X years minimum"
        - Consider variations: "years of experience", "years exp", "yoe"
    2. Relevant years of experience
        - Look for domain-specific experience mentions
        - Consider patterns like "X years in [field]", "X years [technology] experience"
    3. Skills/Qualifications (as list)
        - Include both technical and soft skills
        - Look for skill lists, requirements, "must have", "should have"
    4. Tech stack/tools (as list)
        - Include programming languages, frameworks, tools
        - Look for technology mentions, platforms, software
    5. Job requirements (as list)
        - Include responsibilities, duties, expectations
        - Consider both technical and non-technical requirements
    6. Education qualifications
        - Look for degree requirements, certifications
        - Consider patterns like "Bachelor's", "Master's", "Ph.D.", "degree in"
    7. Location details
        - Extract city, state, country
        - Consider remote/hybrid/onsite mentions
        - Look for location flexibility mentions

    Text: {text}
    Return in JSON format with clear categorization
    """
    response = model.generate_content(prompt)
    try:
        import json
        details = json.loads(response.text)
        return details
    except:
        return None

def generate_response(user_input):
    """Generate response using chat history and context."""
    global chat
    
    try:
        # Extract job information from user input
        job_info = extract_job_info(user_input)
        
        if job_info:
            # Add user's message to chat history
            chat.send_message(user_input, stream=True)
            
            # Get a natural acknowledgment using Gemini
            acknowledgment_prompt = f"""
            Generate a natural, conversational acknowledgment for understanding job details.
            Use variations of phrases like "I understand", "Got it", "Perfect", etc.
            Keep it short (1-2 words) and natural.
            Don't use the same acknowledgment repeatedly.
            Examples: "I see", "Ah, perfect", "Great", "Excellent", "Got it"
            
            Previous message: {user_input}
            """
            try:
                ack_response = model.generate_content(acknowledgment_prompt, stream=True)
                acknowledgment = "".join(chunk.text for chunk in ack_response)
            except:
                acknowledgment = "I understand"
            
            # Prepare context based on extracted information
            context = []
            
            # Add high-confidence information to context
            if job_info['role']['confidence'] >= 0.6:
                context.append(f"you're looking for a {job_info['role']['value']}")
            if job_info['company']['confidence'] >= 0.6:
                context.append(f"at {job_info['company']['value']}")
                
            # Build prompt based on available information
            if context:
                # Get a natural response using chat history
                response_prompt = f"""
                Based on our conversation history and the current context, generate a natural response.
                Start with: "{acknowledgment},"
                
                Information understood:
                {', '.join(context)}
                
                Missing information needed:
                {[info for info in ['role', 'company', 'location', 'experience', 'skills'] 
                  if job_info[info]['confidence'] < 0.6]}
                
                Rules:
                1. Keep it friendly and professional
                2. Validate the understood information naturally
                3. Ask for missing information conversationally
                4. Use varied sentence structures
                5. Add light enthusiasm where appropriate
                6. Keep it concise (2-3 sentences max)
                7. Make it feel like a natural conversation
                8. Reference previous messages when appropriate
                """
                
                try:
                    # Use chat.send_message with streaming
                    chat_response = chat.send_message(response_prompt, stream=True)
                    prompt = "".join(chunk.text for chunk in chat_response)
                except:
                    # Fallback to basic response
                    prompt = f"{acknowledgment}, {', '.join(context)}. "
                    missing_info = []
                    if job_info['role']['confidence'] < 0.6:
                        missing_info.append("job role")
                    if job_info['company']['confidence'] < 0.6:
                        missing_info.append("company name")
                    if job_info['location']['confidence'] < 0.6:
                        missing_info.append("location")
                    if job_info['experience']['confidence'] < 0.6:
                        missing_info.append("experience requirements")
                    if job_info['skills']['confidence'] < 0.6:
                        missing_info.append("required skills")
                        
                    if missing_info:
                        prompt += f"Could you please provide more details about the {', '.join(missing_info)}?"
                
                if not any(missing_info):
                    # If we have all essential information, proceed to generate job posting
                    return generate_job_posting(job_info['role']['value'], job_info['company']['value'], job_info['location'], job_info['experience'], job_info['requirements'], conversation_history)
            else:
                prompt = f"{acknowledgment}, I couldn't quite understand the job details. Could you please specify the role and company more clearly?"
                
            # Add the prompt to chat history with streaming
            chat.send_message(prompt, stream=True)
            return prompt
        else:
            return "I'm having trouble understanding the job details. Could you please rephrase your request?"
            
    except Exception as e:
        print(f"Error in generate_response: {str(e)}")
        # Reset chat history if there's an error
        chat = model.start_chat(history=[])
        return "I encountered an error. Let's start fresh - could you tell me about the job role and company?"

async def generate_job_posting(role, company, location=None, experience=None, requirements=None, conversation_history=None):
    """Generate a job posting using AI with enhanced context."""
    print(f"Generating job posting for {role} at {company}")
    
    # Format location string if it exists
    location_str = ""
    if isinstance(location, dict):
        parts = []
        if location.get('city'):
            parts.append(location['city'])
        if location.get('state'):
            parts.append(location['state'])
        if location.get('country'):
            parts.append(location['country'])
        location_str = ", ".join(filter(None, parts))
    elif location:
        location_str = location

    # Parallel fetch company description
    company_description = await get_company_description_async(company)
    
    # Create context from conversation history
    conversation_context = ""
    if conversation_history:
        conversation_context = "Previous conversation context:\n" + "\n".join([
            f"User: {msg['user']}\nBot: {msg['bot']}" 
            for msg in conversation_history[-3:]  # Use last 3 messages for context
        ])

    # Enhanced prompt with all available information
    prompt = f"""Create a detailed job posting using ALL the following information:

Role: {role}
Company: {company}
Location: {location_str if location_str else 'Location Flexible'}
Experience Required: {experience if experience else 'Not specified'}
Additional Requirements: {', '.join(requirements) if requirements else 'Not specified'}

{conversation_context}

Use this EXACT format and include ALL provided information:

# {role} at {company}{' - ' + location_str if location_str else ''}

## About {company}
{company_description}

## Role Overview
[Write 3-4 sentences describing what the role involves, its impact, and team structure. Include location and experience requirements.]

## Key Responsibilities
* Design and develop scalable solutions
* Collaborate with cross-functional teams
* Lead technical initiatives
* Implement best practices
* Mentor team members
* Drive quality and innovation

## Required Qualifications
* {experience if experience else 'Bachelor\'s degree in Computer Science or related field'}
* Strong programming skills
* Excellent problem-solving abilities
* Team collaboration experience
{f'* Ability to work from {location_str}' if location_str else '* Flexible work location'}
{chr(10).join([f'* {req}' for req in (requirements or [])])}

## Preferred Qualifications
* Master's degree in relevant field
* Experience with cloud platforms
* Leadership experience
* Industry certifications

## Benefits & Perks
* Competitive compensation
* Comprehensive health coverage
* Professional development
* {'Flexible work arrangements' if not location_str else f'Modern office in {location_str}'}
* {'Remote work options' if not location_str else 'Collaborative work environment'}

Replace the above bullet points with specific details relevant to a {role} position at {company}."""

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        generated_text = response.text.strip()
        
        # Verify all sections are present
        required_sections = ['About', 'Role Overview', 'Key Responsibilities', 'Required Qualifications', 'Preferred Qualifications', 'Benefits']
        missing_sections = [section for section in required_sections if section not in generated_text]
        
        if missing_sections or not generated_text.startswith('# '):
            # If sections are missing, use the template with company description
            generated_text = f"""# {role} at {company}{' - ' + location_str if location_str else ''}

## About {company}
{company_description}

## Role Overview
We are seeking an experienced {role} to join our team{' in ' + location_str if location_str else ''}{'. Candidates should have ' + experience if experience else ''}. This position offers an exciting opportunity to make a significant impact while working with cutting-edge technologies. You will work closely with cross-functional teams to deliver innovative solutions.

## Key Responsibilities
* Design and implement scalable solutions for complex technical challenges
* Collaborate with product managers, designers, and other engineers
* Lead technical initiatives and architectural decisions
* Mentor team members and promote best practices
* Participate in code reviews and technical discussions
* Drive quality through testing and documentation

## Required Qualifications
* {experience if experience else 'Bachelor\'s degree in Computer Science or related field'}
* Strong technical expertise in relevant technologies
* Excellent problem-solving and analytical skills
* Strong communication and collaboration abilities
{f'* Ability to work from {location_str}' if location_str else '* Flexible work location'}
{chr(10).join([f'* {req}' for req in (requirements or [])])}

## Preferred Qualifications
* Master's degree in relevant field
* Experience with cloud platforms and distributed systems
* Technical leadership experience
* Industry certifications or specialized training

## Benefits & Perks
* Competitive compensation package
* Comprehensive health and dental coverage
* Professional development opportunities
* {'Flexible work arrangements' if not location_str else f'Modern office in {location_str}'}
* {'Remote work options' if not location_str else 'Collaborative work environment'}
"""
            
        return generated_text
    except Exception as e:
        print(f"Error generating job posting: {str(e)}")
        return None

def format_job_posting(content):
    """Format the job posting with proper HTML and styling."""
    if not content:
        return "<div class='error'>Failed to generate job posting</div>"
    
    print("Original content received for formatting:", content)
        
    # First, normalize line endings and ensure content is clean
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Convert markdown headers with proper spacing and styling
    content = re.sub(r'##\s*(.*?)\s*\n', r'<h2 class="job-section-header">\1</h2>\n', content)
    content = re.sub(r'#\s*(.*?)\s*\n', r'<h1 class="job-title">\1</h1>\n', content)
    
    # Convert bold text
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
    
    # Split content into sections while preserving headers
    sections = []
    current_section = []
    lines = content.split('\n')
    
    for line in lines:
        if line.strip():
            if line.startswith('<h1') or line.startswith('<h2'):
                if current_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
            current_section.append(line)
    if current_section:
        sections.append('\n'.join(current_section))
    
    # Process each section
    processed_sections = []
    for section in sections:
        # Handle bullet points in this section
        if '*' in section:
            # Split section into header and content
            header_match = re.match(r'(<h[12][^>]*>.*?</h[12]>)', section, re.DOTALL)
            if header_match:
                header = header_match.group(1)
                content_part = section[len(header):].strip()
                
                # Convert bullet points to list items
                bullet_points = [line.strip() for line in content_part.split('\n') if line.strip().startswith('*')]
                if bullet_points:
                    formatted_list = '<ul class="job-list">\n' + '\n'.join(
                        f'<li>{point.strip("* ")}</li>' for point in bullet_points
                    ) + '\n</ul>'
                    processed_sections.append(f"{header}\n{formatted_list}")
                else:
                    processed_sections.append(section)
            else:
                processed_sections.append(section)
        else:
            # Handle regular paragraphs
            lines = section.split('\n')
            processed_lines = []
            current_para = []
            
            for line in lines:
                if line.strip():
                    if line.startswith('<h'):
                        if current_para:
                            processed_lines.append(f'<p class="job-paragraph">{" ".join(current_para)}</p>')
                            current_para = []
                        processed_lines.append(line)
                    else:
                        current_para.append(line.strip())
                elif current_para:
                    processed_lines.append(f'<p class="job-paragraph">{" ".join(current_para)}</p>')
                    current_para = []
            
            if current_para:
                processed_lines.append(f'<p class="job-paragraph">{" ".join(current_para)}</p>')
            
            processed_sections.append('\n'.join(processed_lines))
    
    # Join all processed sections
    formatted_content = '\n'.join(processed_sections)
    
    print("Final formatted content:", formatted_content)
    
    # Return container without buttons
    return f'''<div class="job-posting-container">
        <div class="job-posting">
            <div class="job-content">
                {formatted_content}
            </div>
        </div>
    </div>'''

def generate_follow_up_question(extracted_info):
    """Generate conversational follow-up questions based on missing information."""
    
    prompt = f"""
    Generate a natural, conversational follow-up question for a job posting assistant.
    
    Current information:
    {json.dumps(extracted_info, indent=2)}
    
    Rules:
    1. Start with a natural acknowledgment or transition
    2. Validate any information you already have
    3. Ask for missing information in a conversational way
    4. Keep it friendly and professional
    5. Add personality but stay focused
    6. Maximum 2-3 sentences
    7. Vary your language and structure
    
    Example formats:
    - "Thanks for that! While I have [known info], I'd love to hear about [missing info]."
    - "Perfect! I've got [known info] noted. Could you share [missing info]?"
    - "Excellent start! Let's add some details about [missing info] to make this posting really stand out."
    
    Known information: {[k for k, v in extracted_info.items() if v]}
    Missing information: {[k for k, v in extracted_info.items() if not v]}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        # Fallback to basic responses
        if not any([extracted_info.get('role'), extracted_info.get('company'), extracted_info.get('location')]):
            return "I'd be happy to help you create a job posting. Could you tell me about the role you're hiring for?"
        
        missing_info = []
        if not extracted_info.get('role'):
            missing_info.append('role')
        if not extracted_info.get('company'):
            missing_info.append('company')
        if not extracted_info.get('location'):
            missing_info.append('location')
        
        if not missing_info:
            return f"Great! For the {extracted_info['role']} position at {extracted_info['company']}, what kind of experience and skills are you looking for in the ideal candidate?"
        
        if len(missing_info) == 1:
            field = missing_info[0]
            prompts = {
                'role': "Could you let me know which role you're looking to fill?",
                'company': "Which company is this position with?",
                'location': "Where will this position be based? Adding location information typically helps attract more relevant candidates."
            }
            return prompts.get(field, f"Could you specify the {field}?")
        
        missing_str = " and ".join(missing_info)
        return f"Could you tell me more about the {missing_str} for this position?"

def modify_job_posting(original_posting, modification_request):
    """Modify the job posting based on user's request using Gemini."""
    prompt = f"""You are an expert at modifying job postings. Given a job posting and a modification request, generate an updated version.

Current job posting:
{original_posting}

Modification request: {modification_request}

Handle the following types of modifications:
1. Remove entire section (e.g., "remove benefits section")
2. Add new section (e.g., "add a section about work culture")
3. Remove specific point (e.g., "remove the point about travel requirements from responsibilities")
4. Modify specific point/sentence (e.g., "change '5 years experience' to '3 years experience'")
5. Add point to section (e.g., "add health insurance to benefits")
6. Update section content (e.g., "make responsibilities more technical")

Rules:
1. Maintain the same markdown formatting with # for main title and ## for section headers
2. Keep bullet points for lists
3. Preserve all unaffected sections exactly as they are
4. Ensure the changes are precise and only modify what was requested
5. If adding new content, match the style and tone of the existing content
6. Keep the overall structure: title, location, company description, followed by other sections

Return the complete modified job posting."""
    
    try:
        response = model.generate_content(prompt)
        modified = response.text.strip()
        
        # Verify the modification was applied
        verification_prompt = f"""Verify if the following modification was correctly applied:
        Original posting:
        {original_posting}
        
        Requested change:
        {modification_request}
        
        Modified posting:
        {modified}
        
        Return ONLY a JSON object:
        {{
            "success": true/false,
            "error": "error message if failed, null if successful"
        }}"""
        
        verify = model.generate_content(verification_prompt)
        verify_json = json.loads(verify.text.strip())
        
        if verify_json['success']:
            return modified
        else:
            # Try one more time with a more specific prompt
            retry_prompt = f"""The previous modification attempt failed. Please try again with this specific focus:
            
            Original posting:
            {original_posting}
            
            Modification request: {modification_request}
            Error feedback: {verify_json.get('error')}
            
            Focus on making ONLY the requested change while preserving everything else exactly as is."""
            
            retry_response = model.generate_content(retry_prompt)
            return retry_response.text.strip()
            
    except Exception as e:
        print(f"Error modifying job posting: {str(e)}")
        return None

def handle_posting_request(message):
    """Handle user's response to posting the job."""
    intent_prompt = f"""
    Analyse user intent. Analyze if the user wants to modify or post the job posting.
    
    User message: "{message}"
    
    Return JSON:
    {{
        "intent": "modify" or "post",
        "confidence": 0.0-1.0
    }}
    """
    
    try:
        response = model.generate_content(intent_prompt)
        result = json.loads(response.text.strip())
        
        if result['confidence'] < 0.6:
            return {
                "response": "I'm not quite sure if you want to modify the posting or proceed with posting it. Could you please clarify?",
                "isJobPosting": False
            }
        
        if result['intent'] == 'post':
            return {
                "response": "Great! I recommend posting this job on platforms like LinkedIn, Indeed, and your company's career page. Would you like to create another job posting?",
                "isJobPosting": False
            }
        else:  # intent is 'modify'
            if conversation_state.get('final_job_posting'):
                # Use Gemini to analyze the modification request and generate the modified posting
                modification_prompt = f"""
                Analyze the user's request to modify a job posting and generate the modified version.

                Original job posting:
                {conversation_state['final_job_posting']}

                User's modification request:
                "{message}"

                Instructions:
                1. Understand what needs to be modified
                2. Keep the same markdown formatting
                3. Maintain all sections
                4. Make the requested changes while keeping other content intact
                5. Ensure the changes are relevant and professional
                6. Keep at least 2-3 bullet points in list sections
                7. Maintain the overall structure and style

                Return only the complete modified job posting in markdown format.
                """

                try:
                    modification_response = model.generate_content(modification_prompt)
                    modified_posting = modification_response.text.strip()
                    
                    # Verify the modified posting has all required sections
                    required_sections = ['About', 'Role Overview', 'Key Responsibilities', 'Required Qualifications', 'Benefits']
                    missing_sections = [section for section in required_sections if section not in modified_posting]
                    
                    if missing_sections:
                        return {
                            "response": "I couldn't properly modify the job posting while maintaining all required sections. Could you please rephrase your modification request?",
                            "isJobPosting": False
                        }
                    
                    # Update the stored posting and format it
                    conversation_state['final_job_posting'] = modified_posting
                    formatted_posting = format_job_posting(modified_posting)
                    
                    return {
                        "response": "I've updated the job posting based on your request. Here's the modified version:",
                        "job_posting": formatted_posting,
                        "isJobPosting": True,
                        "followUp": "Would you like to make any other changes, or should we proceed with posting?"
                    }
                except Exception as e:
                    print(f"Error modifying job posting: {str(e)}")
                    return {
                        "response": "I had trouble modifying the job posting. Could you please rephrase your request?",
                        "isJobPosting": False
                    }
            
            return {
                "response": "I'm having trouble accessing the job posting. Could you please try again?",
                "isJobPosting": False
            }
    except Exception as e:
        print(f"Error in handle_posting_request: {str(e)}")
        return {
            "response": "I'm having trouble understanding your request. Would you like to modify the job posting or proceed with posting it?",
            "isJobPosting": False
        }

@app.route('/poll_job_posting')
def poll_job_posting():
    """Endpoint to check if job posting generation is complete"""
    if not conversation_state['is_generating']:
        if conversation_state['generation_result']:
            result = conversation_state['generation_result']
            # Clear the result so it's not sent again
            conversation_state['generation_result'] = None
            return jsonify({'ready': True, **result})
    return jsonify({'ready': False})

@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Chat route with improved job posting handling"""
    try:
        data = request.json
        user_input = data.get('message', '').strip()
        
        if not user_input:
            return jsonify({"response": "Please enter a message."})

        # Check if we're in a post-job-posting state
        if conversation_state.get('last_action') == 'showing_posting':
            result = handle_posting_request(user_input)
            conversation_state['last_action'] = 'handling_response'
            return jsonify(result)
        
        # Extract job information with improved confidence
        job_info = run_async(extract_job_info_async)(user_input)
        
        # Store any valid information we've extracted
        if not conversation_state.get('partial_info'):
            conversation_state['partial_info'] = {}
        
        partial_info = conversation_state['partial_info']
        
        # Update partial info with any high-confidence information
        if job_info['role']['confidence'] >= 0.6:
            partial_info['role'] = job_info['role']['value']
        if job_info['company']['confidence'] >= 0.6:
            partial_info['company'] = job_info['company']['value']
        if job_info['location']['confidence'] >= 0.6:
            partial_info['location'] = job_info['location']['value']
        
        # Check what information is still missing
        missing_info_response = generate_missing_info_response(job_info)
        
        if missing_info_response and not conversation_state.get('has_asked_for_info'):
            # First time asking for missing info
            conversation_state['has_asked_for_info'] = True
            return jsonify({
                "response": missing_info_response,
                "isJobPosting": False
            })
        
        # Generate job posting with available information
        role = partial_info.get('role') or job_info['role']['value'] or "Software Engineer"
        company = partial_info.get('company') or job_info['company']['value'] or "the Company"
        location = partial_info.get('location') or job_info['location']['value'] or "Remote"
        
        # Clear the state
        conversation_state['has_asked_for_info'] = False
        conversation_state['partial_info'] = None
        
        # Generate the job posting
        job_posting = run_async(generate_job_posting)(role, company, location, job_info['experience'], job_info['requirements'], conversation_history)
        
        # Debug print to verify content
        print("Generated job posting content:", job_posting)
        
        if not job_posting:
            return jsonify({
                "response": "I encountered an error generating the job posting. Please try again.",
                "isJobPosting": False
            })
        
        # Verify all sections are present and content is complete
        required_sections = ['About', 'Role Overview', 'Key Responsibilities', 'Required Qualifications', 'Benefits']
        missing_sections = [section for section in required_sections if section not in job_posting]
        
        if missing_sections:
            print(f"Missing sections detected: {missing_sections}")
            # Regenerate if missing sections
            job_posting = run_async(generate_job_posting)(role, company, location, job_info['experience'], job_info['requirements'], conversation_history)
            print("Regenerated job posting content:", job_posting)
        
        # Store the complete job posting and update state
        conversation_state['final_job_posting'] = job_posting
        conversation_state['last_action'] = 'showing_posting'
        
        # Format the job posting with proper HTML
        formatted_posting = format_job_posting(job_posting)
        
        # Debug print to verify formatted content
        print("Formatted job posting HTML:", formatted_posting)
        
        return jsonify({
            "response": "I've created a job posting based on your input. Here it is:",
            "job_posting": formatted_posting,
            "isJobPosting": True,
            "followUp": "Would you like to modify any part of this job posting, or would you like to proceed with posting it?"
        })
            
    except Exception as e:
        print(f"Error in chat route: {str(e)}")
        return jsonify({
            "response": "I encountered an error. Please try again with your request.",
            "isJobPosting": False
        })

def generate_missing_info_response(job_info):
    """Generate a friendly message asking only for missing information."""
    missing = []
    
    # Only add truly missing information
    if not job_info['role']['value'] or job_info['role']['confidence'] < 0.6:
        missing.append("job role")
    if not job_info['company']['value'] or job_info['company']['confidence'] < 0.6:
        missing.append("company name")
    if not job_info['location']['value'] or job_info['location']['confidence'] < 0.6:
        missing.append("location")
    
    if not missing:
        return None
    elif len(missing) == 1:
        return f"Could you also provide the {missing[0]}? This will help me create a more targeted job post."
    elif len(missing) == 2:
        return f"Could you also provide the {missing[0]} and {missing[1]}? This will help me create a more complete job post."
    else:
        return f"Could you please provide the {', '.join(missing[:-1])}, and {missing[-1]}? This will help me create a comprehensive job post."

async def get_company_description_async(company_name):
    """Async version of get_company_description with optimized prompt"""
    prompt = f"Describe {company_name} in 2-3 sentences focusing on main business, industry, and notable achievements."
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error getting company description: {str(e)}")
        return f"{company_name} is a company operating in its respective industry."

def main():
    """Main entry point for the bot"""
    try:
        # Run the Flask app
        app.run(host='0.0.0.0', port=5001, debug=True)
    except KeyboardInterrupt:
        print("Bot shutting down...")
    except Exception as e:
        print(f"Error: {e}")
        print("Bot shutting down...")

if __name__ == "__main__":
    main()