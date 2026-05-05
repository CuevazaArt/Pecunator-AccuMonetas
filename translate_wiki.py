import json
import urllib.request
import urllib.parse
import os
import re
from pathlib import Path

def translate_text(text, target_language="en", source_language="es"):
    if not text.strip():
        return text
        
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_language}&tl={target_language}&dt=t&q={urllib.parse.quote(text)}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            translated_text = "".join([sentence[0] for sentence in result[0] if sentence[0]])
            return translated_text
    except Exception as e:
        print(f"Error translating: {e}")
        return text

def translate_markdown_file(file_path):
    print(f"Translating {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into chunks to avoid URL length limits (approx 2000 chars)
    # We split by paragraphs/double newlines to preserve markdown structure somewhat
    chunks = content.split('\n\n')
    translated_chunks = []
    
    for chunk in chunks:
        # Don't translate code blocks or mermaid blocks if possible, 
        # but for simplicity, we translate the whole chunk.
        if chunk.startswith('```') and chunk.endswith('```'):
            translated_chunks.append(chunk)
            continue
            
        # We process chunks of ~1500 chars max
        if len(chunk) > 1500:
            lines = chunk.split('\n')
            trans_lines = []
            for line in lines:
                if len(line) > 1500:
                    trans_lines.append(translate_text(line))
                else:
                    trans_lines.append(translate_text(line))
            translated_chunks.append('\n'.join(trans_lines))
        else:
            translated_chunks.append(translate_text(chunk))
            
    translated_content = '\n\n'.join(translated_chunks)
    
    # Save to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)
        
if __name__ == "__main__":
    wiki_dir = Path(r"c:\Users\lexar\Desktop\Pecunator\wiki")
    for md_file in wiki_dir.glob("*.md"):
        # We skip Home.md as we just modified it partially, but maybe we should translate it too.
        translate_markdown_file(str(md_file))
    print("Done translating wiki.")
