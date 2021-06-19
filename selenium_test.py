import time
from selenium import webdriver
import pandas as pd
import json

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

#looping through check for each invoice
for invoice in range(1, len(total_invoices)+1):
    element = driver.find_element_by_xpath('/html/body/div[4]/form/div[1]/div[1]/table/tbody/tr['+str(invoice)+']/td[3]/a[1]').click()
    try:
        #Find number of rows for looping
        rows = driver.find_elements_by_xpath("/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div[1]/table/tbody/tr")
        num_line_items = len(rows)
        print('num_line_items', num_line_items)
        variance = False
        for i in range(1, (num_line_items)+1):
            print(f'SKU {i}')
            print('-----------------')
            extended_line_cost = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[14]/span[2]').text
            print('extended_line_cost',extended_line_cost)
            adj_item_qty = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[8]/span[2]').text
            print('adjusted item quantity:', adj_item_qty)
            #checking if adj qty input field is filled out
            adj_qty_input_field = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[10]/input')
            x= adj_qty_input_field.get_attribute('value')
            try:
                test = float(x)
            except:
                element = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[10]/input').send_keys(adj_item_qty)        
            # element = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[10]/input').send_keys(adj_item_qty)
            #calculating and input of adjusted unit price
            adj_unit_price = str(float(extended_line_cost) / float(adj_item_qty))
            adj_unit_price_field = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[13]/input')
            x= adj_unit_price_field.get_attribute('value')
            try:
                test = float(x)
            except:
                element = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[13]/input').send_keys(adj_unit_price)
            #element = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[13]/input').send_keys(adj_unit_price)
            #PO Unit Price
            po_unit_price = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[11]/span[2]').text
            #inv price
            inv_price = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[12]/span[1]').text
            #Received Qty
            rec_q = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[8]/span[2]').text
            print('received qty:', rec_q)
            #Quantity
            quantity = driver.find_element_by_xpath('/html/body/div[4]/form/div[3]/div[2]/table/tbody/tr[1]/td/div/div/table/tbody/tr['+str(i)+']/td[9]/span[1]').text
            print('quantity:', quantity)
            #extended PO and invoice cost
            ext_po_cost = float(po_unit_price) * float(rec_q)
            ext_inv_cost = float(inv_price) * float(quantity)
            print('extended_po_cost:', ext_po_cost,'\n extended_invoice_cost',ext_inv_cost)
            #percent difference
            percent_difference = abs((float(ext_po_cost)-float(ext_inv_cost))/float(ext_inv_cost))
            print('percent difference:', percent_difference)
            if percent_difference >= 0.02:
                variance = True
        if variance == True:
            doc_number = driver.find_element_by_xpath('/html/body/div[4]/form/div[1]/div[2]/table[1]/tbody/tr[1]/td/span').text
            save_invoice = driver.find_element_by_xpath('/html/body/div[4]/form/div[4]/div[2]/div/div/div/button[3]').click()
            click_to_queue = driver.find_element_by_xpath('/html/body/div[4]/div[1]/div/div/ul/li[1]/a[1]').click()
            #driver.back()
        else:
            doc_number = driver.find_element_by_xpath('/html/body/div[4]/form/div[1]/div[2]/table[1]/tbody/tr[1]/td/span').text
            save_invoice = driver.find_element_by_xpath('/html/body/div[4]/form/div[4]/div[2]/div/div/div/button[3]').click()
            click_to_queue = driver.find_element_by_xpath('/html/body/div[4]/div[1]/div/div/ul/li[1]/a[1]').click()
    except:

        driver.back()