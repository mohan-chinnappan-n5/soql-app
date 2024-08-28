import streamlit as st
import requests
import pandas as pd
import json
from urllib.parse import urljoin

#------------------------------------------------------
# Salesforce SOQL Query Executor Streamlit Application
# Author: Mohan Chinnappan
# Copyleft software. Maintain the author name in your copies/modifications
#
# Description: This application allows users to execute SOQL queries against
# Salesforce, handle pagination using the nextRecordsUrl key, and display the results
# in a DataFrame. Users can upload an auth.json file for authentication,
# specify the API version, and choose whether to use the Tooling API.
#------------------------------------------------------

def load_auth_credentials(auth_file):
    """
    Loads Salesforce credentials from an auth.json file.

    :param auth_file: Uploaded auth.json file
    :return: Dictionary containing access_token and instance_url
    """
    auth_data = json.load(auth_file)

    # Extract the correct keys for access token and instance URL
    access_token = auth_data.get('access_token') or auth_data.get('accessToken')
    instance_url = auth_data.get('instance_url') or auth_data.get('instanceUrl')

    if not access_token or not instance_url:
        raise ValueError("Missing required credentials in auth.json")

    return {
        'access_token': access_token,
        'instance_url': instance_url
    }

def fetch_data(full_url, headers, instance_url, all_pages):
    """
    Fetches data from a REST API and handles pagination using the nextRecordsUrl key.

    :param full_url: The full API endpoint URL
    :param headers: HTTP headers for the API request
    :param instance_url: The base instance URL to resolve pagination links
    :param all_pages: Boolean flag to indicate whether to fetch all pages
    :return: Tuple of a list of aggregated results and the last page response JSON
    """
    all_records = []
    while full_url:
        response = requests.get(full_url, headers=headers)
        
        if response.status_code != 200:
            st.error(f"Failed to fetch data: {response.status_code} {response.text}")
            return None, None
        
        last_response = response.json()
        all_records.extend(last_response.get('records', []))
        
        # Check for the next page URL if all_pages is True
        if all_pages:
            full_url = last_response.get('nextRecordsUrl', None)
            if full_url:
                full_url = urljoin(instance_url, full_url)
        else:
            break
    
    return all_records, last_response

def main():
    st.title("Salesforce SOQL Query Executor")

    st.sidebar.header("Help Information")
    st.sidebar.write("""
    **To get `auth.json`:**
    1. Login into your org using:
       ```bash
       sf force auth web login -r https://login.salesforce.com
       ```
       or for sandboxes:
       ```bash
       sf force auth web login -r https://test.salesforce.com
       ```
       You will receive the username that got logged into this org in the console/terminal.

    2. Run this command to get `auth.json`:
       ```bash
       sf mohanc hello myorg -u username > auth.json
       ```
    """)

    # Upload auth.json file
    auth_json = st.file_uploader("Upload auth.json file", type=['json'])
    
    if auth_json is not None:
        # Load Salesforce credentials from auth.json
        auth_credentials = load_auth_credentials(auth_json)
        instance_url = auth_credentials['instance_url'].strip()
        
        # Ensure instance_url has the correct scheme
        if not instance_url.startswith(('http://', 'https://')):
            instance_url = 'https://' + instance_url

        # Provide a list of standard SOQL queries

            # Provide a list of standard SOQL queries with multiline support
        standard_queries = {
            "Accounts": """SELECT Id, Name, Type
                                    FROM Account LIMIT 10""",
            "Contacts": """SELECT Id, FirstName, LastName, Email
                                    FROM Contact""",
            "Opportunities": """SELECT Id, Name, StageName, CloseDate
                                        FROM Opportunity
                                        WHERE CloseDate > LAST_YEAR 
                                        LIMIT 10""",
            "Leads": """SELECT Id, FirstName, LastName, Company
                                FROM Lead
                                WHERE Status = 'Open - Not Contacted'
                                ORDER BY CreatedDate DESC
                                LIMIT 10""",
            "Cases": """SELECT Id, CaseNumber, Status, Subject
                                FROM Case
                                WHERE Status != 'Closed'
                                ORDER BY Priority ASC
                                LIMIT 10
                                """,
            "SetupAuditTrail": """SELECT CreatedDate,
                                    CreatedBy.Name, 
                                    CreatedByContext,
                                    CreatedByIssuer,
                                    Display,
                                    Section 
                                    FROM SetupAuditTrail 
                                    LIMIT 100""",
            "GroupMember": """SELECT id,Group.Name,UserOrGroupId FROM GroupMember"""

        }
        


        # Dropdown to select a standard query
        selected_query = st.selectbox("Select a standard SOQL query", list(standard_queries.keys()))

        # Automatically populate the SOQL query text area based on selection
        soql_query = st.text_area("Enter SOQL Query", standard_queries[selected_query])

        # Input field for API version
        api_version = st.text_input("API Version", "60.0")

        # Option to use Tooling API
        use_tooling_api = st.checkbox("Use Tooling API")

        # Option to fetch all pages
        all_pages = st.checkbox("Fetch all pages")

        if st.button("Execute SOQL Query"):
            if not soql_query:
                st.error("SOQL query is required.")
                return
            
            # Determine the correct API endpoint
            endpoint_path = f"/services/data/v{api_version}/query"
            if use_tooling_api:
                endpoint_path = f"/services/data/v{api_version}/tooling/query"
            
            # Form the full API URL with the SOQL query
            full_url = urljoin(instance_url, f"{endpoint_path}?q={soql_query}")
            
            # Set up headers for the API request
            headers = {
                'Authorization': f'Bearer {auth_credentials["access_token"]}',
                'Content-Type': 'application/json'
            }
            
            try:
                # Fetch data from the API
                data, last_response = fetch_data(full_url, headers, instance_url, all_pages)
                
                if data is None:
                    return
                
                # Convert the data to a DataFrame if not empty
                if data:
                    df = pd.DataFrame(data)
                    
                    # Display the DataFrame
                    st.dataframe(df)
                    
                    # Save the DataFrame to a CSV file
                    csv = df.to_csv(index=False).encode('utf-8')
                    
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name='salesforce_data.csv',
                        mime='text/csv'
                    )
                    
                    # Show the formed API URL
                    st.write("**Formed API URL:**")
                    st.code(full_url)
                    
                    # Show the JSON response if available
                    if last_response:
                        st.write("**JSON Response:**")
                        st.json(last_response)
                
                else:
                    st.warning("No data found.")
            
            except Exception as e:
                st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()