import json
import pandas as pd
from pandas.testing import assert_frame_equal
import numpy as np
import requests
from selenium import webdriver
from UnitTest import get_selenium_dict


class Testing_LIR:

 #instantiate a dictionary containing all invoices in queue + invoice ID's needed to dig further into API
    def __init__(self, size = '2'):
        #{token obtained with token request method}
        with open('client_secret.json', 'r') as f:
            self.client_secret = json.load(f)['client_secret']
        self.auth_token, self.refresh_token = Testing_LIR.get_auth_token(self.client_secret)
        self.payload = {}
        self.headers = {'accept': 'application/json','Authorization': f'Bearer {self.auth_token}'}
        lir_url = f'https://test.apiclient.com/CHPAPO/v2/lineitemresolution?size={size}'
        #use credentials to grab all LIR invoices
        response = requests.request("GET", lir_url, headers=self.headers)
        self.invoices_dict= json.loads(response.text)['_embedded']['lineitemresolution']
        #returns the number of invoices to instantiate for entire program
        self.number_invoices = len(self.invoices_dict)

    def get_auth_token(client_secret):
        #get auth and refresh tokens
        url = "https://test.apiclient.com/auth/realms/rest-api/protocol/openid-connect/token"
        payload = f'grant_type=client_credentials&client_id=CHPREST&client_secret={client_secret}'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.request("POST", url, headers=headers, data = payload)
        return json.loads(response.text)['access_token'],  json.loads(response.text)['refresh_token']

class Invoice:

    #loop through an instantiate invoice 'number_invoices' times
    def __init__(self, queue_position, lir_queue):
        self.lir_queue = lir_queue
        self.queue_position = queue_position
        self.document_number = int()
        self.document_amount = float()
        self.approved_amount = float()
        self.freight_amount = float()
        self.document_date = str()
        self.sku_ids = []
        #document ID needed to dig further into API
        self.document_id = lir_queue.invoices_dict[self.queue_position]['id']

    #general invoice information - might be of use later
    def get_job_info(self):
        job_url = lir_queue.invoices_dict[self.queue_position]['_links']['job']['href']
        r = requests.request("GET", job_url, headers=lir_queue.headers, data={})
        job = json.loads(r.text)
        self.document_number = job['documentNumber']
        self.document_amount = job['documentAmount']
        self.approved_amount = job['approvedAmount']
        self.freight_amount = job['freightAmount']
        self.document_date = job['documentDate']


    def sku_matrix_to_df(skus_info, feature_list):
        lst = []
        for feature in feature_list:
            a = [sku[feature] for sku in skus_info]
            lst.append(a)
        lst_t = np.transpose(lst)
        return pd.DataFrame(data = lst_t, columns = feature_list)

    def get_api_sku_info(self):
        #get information entered by CenterViews for each SKU on a given invoice as well as links to PO/receiving data supplied by ChemPoint needed for calculations
        api_sku_infos_url = f'https://test.apiclient.com/CHPAPO/v2/jobs/{self.document_id}/documentdetails'
        sku_infos_request = requests.request("GET", api_sku_infos_url, headers=lir_queue.headers, data={})
        skus_info = json.loads(sku_infos_request.text)['_embedded']['documentdetails']
        #number of SKUs on invoice
        self.number_skus = len(skus_info)
        #populating df object with data below. 
        self.sku_table = Invoice.sku_matrix_to_df(skus_info, ['documentDetailId', 'quantity', 'unitPrice', 'adjustedQuantity', 'adjustedUnitPrice'])
        self.sku_table['documentDetailId'] = self.sku_table['documentDetailId'].astype('int32')
        
        
 
    def get_po_details(self):
        #array containing each SKU's information
        po_df = pd.DataFrame(columns = ['po_detail_id', 'sku_number', 'sku_description', 'po_price'])
        for sku_id in self.sku_table.documentDetailId:
            sku_po_url = f'https://test.apiclient.com/CHPAPO/v2/documentdetails/{int(sku_id)}/podetail'
            po_sku_request = requests.request("GET", sku_po_url, headers=lir_queue.headers, data={})
            po_sku_response = json.loads(po_sku_request.text)
            po_detail_id, sku_number, sku_description, po_price = po_sku_response['poDetailId'], po_sku_response['itemNumber'], po_sku_response['itemDescription'], po_sku_response['unitPrice']
            d = {}
            d['po_detail_id'] = po_detail_id
            d['sku_number'] = sku_number
            d['sku_description'] = sku_description
            d['po_price'] = po_price
            po_df = po_df.append(d, ignore_index=True)
        # join resulting df to self.pandas df
        self.sku_table = self.sku_table.join(po_df)
 

    def get_receiving_details(self):
        #array containing each SKU's information
        rec_df = pd.DataFrame(columns = ['detail_id', 'rec_qty'])
        for sku_id in self.sku_table.documentDetailId:
            sku_receiving_url = f'https://test.apiclient.com/CHPAPO/v2/documentdetails/{int(sku_id)}/receivingdetail'
            sku_rec_request = requests.request("GET", sku_receiving_url, headers=lir_queue.headers, data={})
            sku_rec_response = json.loads(sku_rec_request.text)
            detail_id, rec_qty = sku_rec_response['receivingDetailId'], sku_rec_response['receivingQuantity']
            d = {}
            d['po_detail_id'] = detail_id
            d['rec_qty'] = rec_qty
            rec_df = rec_df.append(d, ignore_index=True)
        # join resulting df to self.pandas df
        self.sku_table = self.sku_table.join(rec_df, rsuffix='r', lsuffix='l')

 

    def calculate_cost(self):
        self.sku_table['adjustedQuantity'] = self.sku_table['rec_qty']
        self.sku_table['extended_sku_cost'] = self.sku_table['quantity'] * self.sku_table['unitPrice']
        self.sku_table['adjustedUnitPrice'] = self.sku_table['extended_sku_cost'] / self.sku_table['adjustedQuantity']
        self.sku_table['adjustedQuantity'] = self.sku_table['rec_qty']
        self.sku_table['extended_sku_cost'] = self.sku_table['quantity'] * self.sku_table['unitPrice']
        self.sku_table['adjustedUnitPrice'] = self.sku_table['extended_sku_cost'] / self.sku_table['adjustedQuantity']
        self.sku_table['ext_po_cost']= self.sku_table['po_price'] * self.sku_table['rec_qty']
        self.sku_table['percent_difference'] = abs(self.sku_table['ext_po_cost'] - self.sku_table['extended_sku_cost']) / (self.sku_table['extended_sku_cost'])
 
    def invoice2df(queue_position, queue):
        #returns invoice number and generated invoice dataframe with calculated values
        invoice = Invoice(queue_position, queue)
        invoice.get_job_info() 
        invoice.get_api_sku_info() 
        invoice.get_po_details() 
        invoice.get_receiving_details() 
        invoice.calculate_cost() 
        

    def patch_data(self):
        #Patch data, SKU by SKU
        for idx, sku_id in enumerate(self.sku_table.documentDetailId):
            #etag is needed for 'if-match' header required for PATCH operation
            etag_url = f"https://test.apiclient.com/CHPAPO/v2/documentdetails/{sku_id}"
            payload = ""
            etag = requests.request("GET", etag_url, headers=lir_queue.headers, data=payload).headers['Etag']
            adjusted_qty_topatch = str(self.sku_table['adjustedQuantity'][idx])
            adjusted_price_topatch = str(self.sku_table['adjustedUnitPrice'][idx])
            patch_payload = json.dumps([{"path": "/adjustedQuantity","op": "replace","value": adjusted_qty_topatch},{"path": "/adjustedUnitPrice","op": "replace","value": adjusted_price_topatch}])
            patch_headers = {
                            "accept": "application/json",
                            "Authorization": f"Bearer {lir_queue.auth_token}",
                            "If-Match": etag,
                            "Content-Type": "application/json-patch+json"}
            patch_request = requests.request("PATCH", etag_url, headers=patch_headers, data=patch_payload)

    def compare_dfs(selenium_df, api_df, document_number):
        #Input is one selenium df and one REST df. Standardizes the two so they can be compared. Tests for equality between the two dataframes
        
        selenium_df = selenium_df.sort_values(by = 'sku_number')
        selenium_df = selenium_df.reset_index(drop=True)
        selenium_df = selenium_df.astype(float)
        selenium_df.columns =  ['quantity', 'unitPrice', 'adjustedQuantity', 'adjustedUnitPrice',
        'sku_number', 'po_price', 'rec_qty', 'extended_sku_cost', 'ext_po_cost',
        'percent_difference']
        
        api_df = api_df.drop(columns = ['documentDetailId', 'po_detail_idl', 'sku_description', 'detail_id', 'po_detail_idr'])
        api_df = api_df.sort_values(by = 'sku_number')
        api_df = api_df.reset_index(drop=True)
        api_df = api_df.astype(float)
        t = (api_df.values == selenium_df.values).all()
        return document_number, t

    def test(api_dict, selenium_dict):
        #create df for all invoices in LIR queue using existing Selenium project
        #Compare each value to the new method and create a list of errors + return an error percentage
        #Make a nice GUI showing error progress if time
        equal_keys = set(api_dict.keys()).intersection(set(selenium_dict.keys()))
        test_results = []
        for document_number in equal_keys:
            t = Invoice.compare_dfs(selenium_dict[str(document_number)], api_dict[str(document_number)], str(document_number))
            test_results.append(t)
        return test_results

#instantiate the queue and grab credentials to access REST API
lir_queue = Testing_LIR(size='20')
#dictionary filled with invoices and corresponding data
api_dict = {}
for queue_position in range(lir_queue.number_invoices):
    invoice = Invoice(queue_position, lir_queue)
    invoice.get_job_info()
    invoice.get_api_sku_info()
    invoice.get_po_details()
    invoice.get_receiving_details()
    invoice.calculate_cost()
    invoice.patch_data()
    api_dict[invoice.document_number] = invoice.sku_table

#testing for equality. Will return list of tuples, each with doc num and bool 
selenium_dict = get_selenium_dict()
Invoice.test(api_dict, selenium_dict)