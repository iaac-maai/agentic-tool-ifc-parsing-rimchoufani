[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/tZ_53IY8)
[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=22954097&assignment_repo_type=AssignmentRepo)
# Gemini Tool Example

A simple demonstration of using function calling with Google's Gemini API.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your Gemini API key:
```bash
cp .env.example .env
```

Then edit `.env` and add your API key:
```
GEMINI_API_KEY=your-actual-api-key-here
```

Get your API key from: https://makersuite.google.com/app/apikey

## Usage

Run the example:
```bash
python gemini_tool_example.py
```

## What it does

The example creates a simple calculator tool that Gemini can use to perform arithmetic operations. The model will automatically call the tool when needed to answer mathematical questions.

## Customizing

To add your own tool, modify the `calculate_tool` schema and implement your function. The tool schema follows the Gemini function calling format:

```python
your_tool = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="your_function_name",
            description="What your function does",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "param_name": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="Parameter description"
                    )
                },
                required=["param_name"]
            )
        )
    ]
)
```
