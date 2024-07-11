import mysql.connector
import os
import random
import cv2
import pytesseract
import re
import numpy as np
import string
from datetime import datetime

def increase_brightness(image, value=30):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    v = cv2.add(v, value)
    v[v > 255] = 255
    v[v < 0] = 0
    final_hsv = cv2.merge((h, s, v))
    image = cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)
    return image

def correct_first_character(result):
    if result.startswith('3'):
        return '9' + result[1:]
    return result

def validate_plate_format(text):
    match = re.match(r'^(\d{2})([A-Z]+)(\d+)$', text)
    if match:
        return match.group(0)
    return ""

#Connecting to database
mydb = mysql.connector.connect(
    host='localhost',
    user='root',
    password='Sarapython1!',
    database='car_plate'
)

cursor = mydb.cursor()

image_directory = os.path.join(os.path.expanduser('~'), 'Desktop', 'programming')

#List for images
images = []

for image_file in os.listdir(image_directory):
    if image_file.endswith(('png', 'jpg', 'jpeg', 'gif')):
        image_path = os.path.join(image_directory, image_file)
        images.append(image_path)

#Choosing images randomly
rand_image = random.choice(images)

#Tesseract modifications
image = cv2.imread(rand_image)
image = increase_brightness(image)
image = cv2.filter2D(image, -1, np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
gray = cv2.GaussianBlur(gray, (5, 5), 0)
kernel = np.ones((3, 3), np.uint8)
dilated = cv2.dilate(gray, kernel, iterations=1)
eroded = cv2.erode(dilated, kernel, iterations=1)
gray = cv2.threshold(eroded, 127, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

config = "--oem 3 --psm 6"
result = pytesseract.image_to_string(gray, config=config).strip(string.ascii_lowercase)
result = result.replace('\n', '').replace('\r', '').strip(string.ascii_lowercase)
remove_chars = "|'`“ [] = + - / ° ~"
result = result.strip(remove_chars)
result = result.replace('g', '9')
result = re.sub(r'[^A-Z0-9\s]', '', result)
result = result.replace(' ', '')

#Extracting the text from the image
extracted_text = validate_plate_format(result)

if extracted_text:
    print(f"\nExtracted Text: {extracted_text}")

    #Sending query to the database
    query = """
    SELECT p.id, u.id, u.name, p.expired_at 
    FROM plates p 
    JOIN users u ON p.user_id = u.id 
    WHERE p.number = %s"""
    cursor.execute(query, (extracted_text,))
    result = cursor.fetchone()
    if result:
        plate_id, user_id, user_name, expired_at = result

        #changed type of expired_at
        expired_at = datetime.combine(expired_at, datetime.min.time())

        #user cannot enter if plate expired
        if datetime.now() >= expired_at:
            print(f"Sorry {user_name}, your entrance has expired. Please buy the ticket again.")
        else:
            #Checking the place details matching user id
            place_query = """
                SELECT floor, parking_lot_name FROM places WHERE user_id = %s
                """
            cursor.execute(place_query, (user_id,))
            place_result = cursor.fetchone()

            if place_result:
                floor, parking_lot_name = place_result
                message = f"Hello {user_name}, your floor is {floor} at {parking_lot_name}."
                print(message)

                #Updating time when user enters
                enter_time = """UPDATE logs SET entered_at = NOW() WHERE plate_id = %s"""
                cursor.execute(enter_time, (plate_id,))
                mydb.commit()
            else:
                print(f"No place information is provided for {user_name}.")
    else:
        print("No matching plate number found.")

mydb.commit()

cursor.close()
mydb.close()


