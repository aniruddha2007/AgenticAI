import Lanchain_helper as helper
import streamlit as st
st.title("Restaurant Name Generator")

cuisine = st.sidebar.selectbox("Pick a cuisine", ("Italian","Indian","Chinese","Japanese","French","Mexican","Thai","Greek","Korean","Spanish","American","Vietnamese","Turkish","Lebanese","Brazilian","Moroccan","Ethiopian","German","Indonesian","Caribbean"))


if cuisine:
    response = helper.generate_restaurant_name_and_items(cuisine)

    st.header(response['restaurant_name'])
    menu_items = response['menu_items'].split(",")
    st.write("**MENU ITEMS**")
    for item in menu_items:
        st.write("*", item)
    
