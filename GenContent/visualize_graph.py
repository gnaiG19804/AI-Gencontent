
import sys
import os
from pathlib import Path

# Add project root to path so we can import services
sys.path.insert(0, str(Path(__file__).parent))

from services.genConten import genContent, ContentState
from langgraph.graph import StateGraph, END
from services.genConten import generate_node, review_node, should_continue

# Re-construct the graph logic exactly as in genConten.py to visualize it
# (We can't easily import 'app' since it's inside the function, so we reconstruct the structure)

def build_graph():
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
    return workflow.compile()

def visualize():
    try:
        app = build_graph()
        
        # Get graph image
        graph_png = app.get_graph().draw_mermaid_png()
        
        output_path = "langgraph_workflow.png"
        with open(output_path, "wb") as f:
            f.write(graph_png)
            
        print(f"✅ Created visualization: {os.path.abspath(output_path)}")
        
    except Exception as e:
        print(f"❌ Failed to visualize: {e}")
        print("Note: You need 'langgraph' and 'graphviz' installed.")

if __name__ == "__main__":
    visualize()
