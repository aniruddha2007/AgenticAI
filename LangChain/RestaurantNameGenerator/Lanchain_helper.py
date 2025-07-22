from LangChain.RestaurantNameGenerator.secret_key import openai_key
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.chains import SequentialChain
import os

os.environ['OPENAI_API_KEY'] = openai_key



llms = OpenAI(temperature=0.7)
# temperature param:- ratio of creative model
# 1 is risky model but creative. Mostly used 0.6 or 0.9
# 0 no risk

def generate_restaurant_name_and_items(cuisine):
    
    # Chain 1 Resto Name
    prompt_template_name = PromptTemplate(
        input_variables= ['cuisine'],
        template= "I want to open restaturant for {cuisine} food. Suggest a fancy name for this."
        )
    name_chain = LLMChain(llm=llms, prompt=prompt_template_name, output_key="restaurant_name")

    # Chain 2
    prompt_template_name = PromptTemplate(
        input_variables= ['restaurant_name'],
        template= """Suggest some menu items for {restaurant_name}. """
        )
    food_items_chain = LLMChain(llm=llms, prompt=prompt_template_name, output_key="menu_items")

    chain = SequentialChain(
        chains = [name_chain, food_items_chain],
        input_variables = ['cuisine'],
        output_variables = ['restaurant_name', 'menu_items']
    )

    response = chain({'cuisine': cuisine})

    return response

if __name__ == "__main__":
    print(generate_restaurant_name_and_items("Indian"))