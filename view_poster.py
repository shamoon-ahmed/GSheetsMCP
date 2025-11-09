#!/usr/bin/env python3
"""
Simple script to decode base64 image and save as PNG file
"""
import base64
import io
import os
from PIL import Image

def save_base64_image(base64_string, filename="generated_poster.png"):
    """
    Convert base64 string to image file
    
    Args:
        base64_string: The base64 encoded image string
        filename: Output filename (default: generated_poster.png)
    """
    try:
        # Remove the data URL prefix if present
        if base64_string.startswith('data:image/'):
            base64_string = base64_string.split(',')[1]
        
        # Decode base64 to bytes
        image_data = base64.b64decode(base64_string)
        
        # Create PIL Image from bytes
        image = Image.open(io.BytesIO(image_data))
        
        # Save as PNG file
        image.save(filename)
        print(f"✅ Image saved as: {filename}")
        print(f"📂 Location: {os.path.abspath(filename)}")
        
        # Show image info
        print(f"📊 Image size: {image.size}")
        print(f"📊 Image mode: {image.mode}")
        
    except Exception as e:
        print(f"❌ Error saving image: {e}")

if __name__ == "__main__":
    # Read base64 string from external file to prevent VS Code lag
    try:
        with open("poster_data.txt", "r") as f:
            base64_image = f.read().strip()
        
        print("📂 Reading base64 data from poster_data.txt...")
        
        # Remove any whitespace and newlines
        base64_image = base64_image.replace('\n', '').replace(' ', '').replace('\r', '')
        
        if base64_image and len(base64_image) > 100:  # Check if we have actual data
            print(f"📊 Base64 data length: {len(base64_image)} characters")
            save_base64_image(base64_image, "generated_poster_image.png")
        else:
            print("❌ No valid base64 data found in poster_data.txt")
            print("💡 Please paste your base64 string into poster_data.txt file")
            
    except FileNotFoundError:
        print("❌ poster_data.txt file not found!")
        print("💡 Create poster_data.txt and paste your base64 string there")
    except Exception as e:
        print(f"❌ Error reading file: {e}")