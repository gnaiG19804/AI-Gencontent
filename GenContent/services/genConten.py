import sys
import json
from pathlib import Path
from typing import Dict, Any, List, TypedDict, Optional, Literal

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.model import ShopifyProduct, ShortDescriptionOutput, LongDescriptionOutput, GenerationMetadata, AIContentEngineOutput
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from config.config import Config
from utils.taxonomy_manager import get_or_refresh_categories
from llms.llm import llm_genContent, llm_reviewer
from datetime import datetime


class ContentState(TypedDict):
    input_data: Dict[str, Any]
    system_prompt: str
    categories_instruction: str
    generated_content: Optional[Dict[str, Any]]
    feedback: Optional[str]
    retry_count: int
    final_status: Literal["success", "failed"]
    metadata: Dict[str, Any]


def generate_node(state: ContentState) -> ContentState:
    print(f"🚀 [Generator] Generating content (Attempt {state['retry_count'] + 1})...")
    
    parser = JsonOutputParser(pydantic_object=ShopifyProduct)
    
    # Context building
    product_info = "\n".join([f"- {key}: {value}" for key, value in state['input_data'].items() if value is not None])
    
    # Add feedback if retrying
    feedback_context = ""
    if state['retry_count'] > 0 and state['feedback']:
        feedback_context = f"\n\nPREVIOUS ATTEMPT REJECTED. FEEDBACK:\n{state['feedback']}\n\n-> YOU MUST FIX ISSUES BASED ON FEEDBACK."

    template = """{system_prompt}

        {categories_instruction}

        Based on the following product information:
        {product_info}

        {feedback_context}

        {format_instructions}
        """
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["system_prompt", "product_info", "categories_instruction", "feedback_context"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain = prompt | llm_genContent | parser
    
    try:
        result = chain.invoke({
            "system_prompt": state['system_prompt'],
            "product_info": product_info,
            "categories_instruction": state['categories_instruction'],
            "feedback_context": feedback_context
        })
        
        # Normalize result keys just in case
        return {
            **state,
            "generated_content": result,
            "metadata": {
                "model": Config.NameModel,
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        print(f"⚠️ Generator Error: {e}")
        return {**state, "generated_content": None} # Will likely fail review


def review_node(state: ContentState) -> ContentState:
    print(f"🧐 [Reviewer] Evaluating content...")
    
    content = state.get("generated_content")
    if not content:
        return {**state, "feedback": "Content generation failed (null output)", "retry_count": state['retry_count'] + 1}
    
    # Review Logic
    review_prompt = f"""
                        You are a Content Quality Assurance Auditor.
                        
                        Review the following product content for Shopify:
                        Title: {content.get('title')}
                        Short Description: {content.get('approved_short_description')}
                        Long Description: {content.get('approved_long_description')}
                        Tags: {content.get('tags')}
                        Product Type: {content.get('product_type')}
                        
                        CRITERIA for APPROVAL:
                        1. Language must be {Config.LANGUAGE}.
                        2. No HTML syntax errors.
                        3. Professional tone, no spammy keywords.
                        4. MUST have a valid product_type selected (from the provided list).
                        
                        Output JSON ONLY:
                        {{
                            "approved": boolean,
                            "feedback": "string explaining reason if rejected, or 'OK' if approved"
                        }}
                        """
    
    try:
        response = llm_reviewer.invoke(review_prompt)
        # Parse JSON from response
        # Simple parsing logic (assuming LLM behaves)
        response_text = response.content.strip()
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        review_result = json.loads(response_text[start:end])
        
        approved = review_result.get("approved", False)
        feedback = review_result.get("feedback", "No feedback provided")
        
        if approved:
            print(" Content APPROVED.")
            return {**state, "feedback": None, "final_status": "success"}
        else:
            print(f" Content REJECTED: {feedback}")
            return {**state, "feedback": feedback, "retry_count": state['retry_count'] + 1}
            
    except Exception as e:
        print(f" Reviewer Error: {e}")
        # Default to reject if reviewer fails
        return {**state, "feedback": f"Reviewer system error: {str(e)}", "retry_count": state['retry_count'] + 1}


def should_continue(state: ContentState) -> Literal["generate", "end"]:
    if state['final_status'] == "success":
        return "end"
    if state['retry_count'] >= 2: # Max 2 retries
        print(" Max retries reached. Failing.")
        return "end"
    return "generate"


async def genContent(model, system_prompt: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate content using LangGraph (Generate -> Review -> Retry) [ASYNC]
    """
    
    # 1. Prepare Categories Context (Blocking I/O but fast/cached, keep sync for now or wrap)
    shopify_categories = get_or_refresh_categories()
    if shopify_categories:
        types_list = "\n".join([f"  - {cat['name']}" for cat in shopify_categories])
        categories_instruction = f"""
            MATCHING SHOPIFY CATEGORIES LIST:
            {types_list}

            => YOU MUST CHOOSE 1 CATEGORY FROM THE LIST ABOVE (product_type).
            Select the MOST ACCURATE category for this product.
            """
    else:
        categories_instruction = "=> Please propose a suitable product_type for this product."

    # 2. Initialize State
    initial_state: ContentState = {
        "input_data": data,
        "system_prompt": system_prompt,
        "categories_instruction": categories_instruction,
        "generated_content": None,
        "feedback": None,
        "retry_count": 0,
        "final_status": "failed", # default
        "metadata": {}
    }
    
    # 3. Build Graph
    workflow = StateGraph(ContentState)
    workflow.add_node("generate", generate_node)
    workflow.add_node("review", review_node)
    
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "review")
    
    workflow.add_conditional_edges(
        "review",
        should_continue,
        {
            "generate": "generate",
            "end": END
        }
    )
    
    app = workflow.compile()
    
    # 4. Run Graph asynchronously
    try:
        result_state = await app.ainvoke(initial_state)
        
        # 5. Format Output
        if result_state['final_status'] == "success" and result_state['generated_content']:
            return {
                "status": "success",
                **result_state['generated_content'],
                "metadata": result_state['metadata']
            }
        else:
            return {
                "status": "error",
                "message": f"Generation failed after retries. Last feedback: {result_state.get('feedback')}"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Graph execution error: {str(e)}"
        }
