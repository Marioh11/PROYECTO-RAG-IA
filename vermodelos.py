import google.generativeai as genai

genai.configure(api_key="AIzaSyBCpWoda8CEQTvQJVH3YaIaTOfRl3GkdWs")

for m in genai.list_models():
    print(m.name)