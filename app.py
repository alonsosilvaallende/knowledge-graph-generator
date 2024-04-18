#from dotenv import load_dotenv, find_dotenv
#_ = load_dotenv(find_dotenv())

import solara
from typing import Any, Callable, Optional, TypeVar, Union, cast, overload, List
from typing_extensions import TypedDict
import time
import ipyvue
import reacton
from solara.alias import rv as v
import os
import openai
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field
from graphviz import Digraph



from langsmith import traceable
from langsmith.wrappers import wrap_openai

# NEEDED FOR INPUT TEXT AREA INSTEAD OF INPUT TEXT
def use_change(el: reacton.core.Element, on_value: Callable[[Any], Any], enabled=True):
    """Trigger a callback when a blur events occurs or the enter key is pressed."""
    on_value_ref = solara.use_ref(on_value)
    on_value_ref.current = on_value
    def add_events():
        def on_change(widget, event, data):
            if enabled:
                on_value_ref.current(widget.v_model)
        widget = cast(ipyvue.VueWidget, solara.get_widget(el))
        if enabled:
            widget.on_event("blur", on_change)
            widget.on_event("keyup.enter", on_change)
        def cleanup():
            if enabled:
                widget.on_event("blur", on_change, remove=True)
                widget.on_event("keyup.enter", on_change, remove=True)
        return cleanup
    solara.use_effect(add_events, [enabled])


@solara.component
def InputTextarea(
    label: str,
    value: Union[str, solara.Reactive[str]] = "",
    on_value: Callable[[str], None] = None,
    disabled: bool = False,
    password: bool = False,
    continuous_update: bool = False,
    error: Union[bool, str] = False,
    message: Optional[str] = None,
):
    reactive_value = solara.use_reactive(value, on_value)
    del value, on_value
    def set_value_cast(value):
        reactive_value.value = str(value)
    def on_v_model(value):
        if continuous_update:
            set_value_cast(value)
    messages = []
    if error and isinstance(error, str):
        messages.append(error)
    elif message:
        messages.append(message)
    text_area = v.Textarea(
        v_model=reactive_value.value,
        on_v_model=on_v_model,
        label=label,
        disabled=disabled,
        type="password" if password else None,
        error=bool(error),
        messages=messages,
        solo=True,
        hide_details=True,
        outlined=True,
        rows=1,
        auto_grow=True,
    )
    use_change(text_area, set_value_cast, enabled=not continuous_update)
    return text_area

# EXTRACTION
openai.api_key = os.environ['OPENAI_API_KEY']

# Wrap the OpenAI client with LangSmith
client = wrap_openai(OpenAI())

# Patch the client with instructor
client = instructor.from_openai(client, mode=instructor.Mode.TOOLS)

class Node(BaseModel):
    id: int
    label: str
    color: str

class Edge(BaseModel):
    source: int
    target: int
    label: str
    color: str = "black"

class KnowledgeGraph(BaseModel):
    nodes: List[Node] = Field(description="Nodes in the knowledge graph")
    edges: List[Edge] = Field(description="Edges in the knowledge graph")

class MessageDict(TypedDict):
    role: str
    content: str

def add_chunk_to_ai_message(chunk: str):
    messages.value = [
        *messages.value[:-1],
        {
            "role": "assistant",
            "content": chunk,
        },
    ]

import ast

# DISPLAYED OUTPUT
@solara.component
def ChatInterface():
    with solara.lab.ChatBox():
        if len(messages.value)>0:
            if messages.value[-1]["role"] != "user":
                obj = messages.value[-1]["content"]
                if f"{obj}" != "":
                    obj = ast.literal_eval(f"{obj}")
                    dot = Digraph(comment="Knowledge Graph")
                    if obj['nodes'] not in [None, []]:
                        if obj['nodes'][0]['label'] not in [None, '']:
                            for i, node in enumerate(obj['nodes']):
                                if obj['nodes'][i]['label'] not in [None, '']:
                                    dot.node(
                                        name=str(obj['nodes'][i]['id']), 
                                        label=obj['nodes'][i]['label'], 
                                        color=obj['nodes'][i]['color']
                                    )
                    if obj['edges'] not in [None, []]:
                        if obj['edges'][0]['label'] not in [None, '']:
                            for i, edge in enumerate(obj['edges']):
                                if obj['edges'][i]['source'] not in [None,''] and obj['edges'][i]['target'] not in [None,''] and obj['edges'][i]['label'] not in [None,'']:
                                    dot.edge(
                                        tail_name=str(obj['edges'][i]['source']), 
                                        head_name=str(obj['edges'][i]['target']), 
                                        label=obj['edges'][i]['label'], 
                                        color=obj['edges'][i]['color']
                                    )
                    with solara.Card():
                        solara.display(dot)

messages: solara.Reactive[List[MessageDict]] = solara.reactive([])
aux = solara.reactive("")
text_block = solara.reactive("Alice loves Bob while Charles hates both Alice and Bob.")
@solara.component
def Page():
    title = "Knowledge Graph Generator"
    with solara.Head():
        solara.Title(f"{title}")
    with solara.Column(style={"width": "100%", "padding": "50px"}):
        solara.Markdown(f"#{title}")
        solara.Markdown("Enter some text and the language model will try to describe it as a knowledge graph. Done with :heart: by [alonsosilva](https://twitter.com/alonsosilva)")
        user_message_count = len([m for m in messages.value if m["role"] == "user"])
        def send():
            messages.value = [*messages.value, {"role": "user", "content": " "}]
        def response(message):
            extraction_stream = client.chat.completions.create_partial(
                model="gpt-3.5-turbo",
                response_model=KnowledgeGraph,
                messages=[
                    {
                        "role": "user",
                        "content": f"Help me understand the following by describing it as small knowledge graph: {text_block.value}. It is important to add variety of colors in the nodes.",
                    },
                ],
                temperature=0,
                stream=True,
            )
            for extraction in extraction_stream:
                obj = extraction.model_dump()
                if f"{obj}" != aux.value:
                    add_chunk_to_ai_message(f"{obj}")
                    aux.value = f"{obj}"
        def result():
            if messages.value != []:
                if messages.value[-1]["role"] == "user":
                    response(messages.value[-1]["content"])
        result = solara.lab.use_task(result, dependencies=[user_message_count])
        InputTextarea("Enter text:", value=text_block, continuous_update=False)
        solara.Button(label="Generate Knowledge Graph", on_click=send)
        ChatInterface()
Page()
