import time
from selenium import webdriver
import pandas as pd
import json


def get_selenium_dict():
    driver = webdriver.Chrome(r'C:\Users\nicks\OneDrive\Documents\Projects\LineItemRes\chromedriver.exe')  # Optional argument, if not specified will search path.
    #log in
    driver.get('https://test.apiclient.com/CHPAPO/login.html#/')

    with open(r'test_login_credentials.json', 'r') as f:
                creds = json.load(f)
                login = creds['username']
                password = creds['password']

    element = driver.find_element_by_xpath('/html/body/div/div/div/div/section[1]/form/fieldset/input[1]').send_keys(login)
    element = driver.find_element_by_xpath('/html/body/div/div/div/div/section[1]/form/fieldset/input[2]').send_keys(password)
    time.sleep(1)

    #Pull up Line item Resolution Page
    element = driver.find_element_by_xpath('/html/body/div/div/div/div/section[1]/form/fieldset/input[3]').click()
    time.sleep(1)
    driver.get('https://test.apiclient.com/CHPAPO/work/activitydetails.html?screenId=LINE_ITEM_RESOLUTION_SCREEN.QUEUE#/')
    time.sleep(1)
    total_invoices = driver.find_elements_by_xpath('/html/body/div[4]/form/div[1]/div/table/tbody/tr')

    #make dictionary with invoice_number key and invoice data
    selenium_dict = {}

    #looping through check for each invoice
    for invoice in range(1, len(total_invoices)+1):
        element = driver.find_element_by_xpath('/html/body/div[4]/form/div[1]/div[1]/table/tbody/tr['+str(invoice)+']/td[3]/a[1]').click()
        try:
            #Find number of SKUs for looping
            rows = driver.find_elements_by_xpath("/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div[1]/table/tbody/tr")
            num_line_items = len(rows)
            variance = False
            df = pd.DataFrame(columns = ['quantity', 'inv_price', 'adj_item_qty', 'adj_unit_price', 'sku_number', 'po_unit_price', 'rec_q', 'ext_inv_cost', 'ext_po_cost', 'percent_difference'])
            for i in range(1, (num_line_items)+1):
                sku_number = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[6]').text
                extended_line_cost = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[14]/span[2]').text
                adj_item_qty = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[8]/span[2]').text
                #checking if adj qty input field is filled out
                adj_qty_input_field = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[10]/input')
                x= adj_qty_input_field.get_attribute('value')
                try:
                    test = float(x)
                except:
                    element = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[10]/input').send_keys(adj_item_qty)        
                #calculating and input of adjusted unit price
                adj_unit_price = float(extended_line_cost) / float(adj_item_qty)
                adj_unit_price_field = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[13]/input')
                x= adj_unit_price_field.get_attribute('value')
                try:
                    test = float(x)
                except:
                    element = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[13]/input').send_keys(adj_unit_price)
                    adj_unit_price = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[13]/input').text
                po_unit_price = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[11]/span[2]').text
                inv_price = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[12]/span[1]').text
                rec_q = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[8]/span[2]').text
                quantity = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[9]/span[1]').text
                ext_po_cost = float(po_unit_price) * float(rec_q)
                ext_inv_cost = float(inv_price) * float(quantity)
                percent_difference = abs((float(ext_po_cost)-float(ext_inv_cost))/float(ext_inv_cost))
                adj_unit_price = float(ext_inv_cost) / float(adj_item_qty)
                arr = [quantity, inv_price, adj_item_qty, adj_unit_price, sku_number, po_unit_price, rec_q, ext_inv_cost, ext_po_cost, percent_difference]
                df = df.append(dict(zip(df.columns, arr)), ignore_index=True)
            
            doc_number = driver.find_element_by_xpath('/html/body/div[4]/form/div[1]/div[2]/table[1]/tbody/tr[1]/td/span').text
            selenium_dict[doc_number] = df
            save_invoice = driver.find_element_by_xpath('/html/body/div[4]/form/div[4]/div[2]/div/div/div/button[3]').click()
            click_to_queue = driver.find_element_by_xpath('/html/body/div[4]/div[1]/div/div/ul/li[1]/a[1]').click()
        except:
            time.sleep(1)
            driver.back()
            time.sleep(1)
    return selenium_dict