import smartcar
import time
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe
import cv2
import json
import smtplib
from email.mime.text import MIMEText
import numpy as np

# CNN stuff
from PIL import Image, ImageFont, ImageDraw
from pycoral.adapters import common
from pycoral.adapters import detect
from pycoral.utils.dataset import read_label_file
from pycoral.utils.edgetpu import make_interpreter
import numpy

# Needed for transferring the image to the Server
import socket
import base64

#HOST = '192.168.0.109'    # The remote host
HOST = 'localhost'    # The remote host
PORT = 50007              # The same port as used by the server

# Prepare the model
model = "numbersRecognitionModel.tflite"
CLASSES = ["1","2", "3", "4", "5", "6", "7", "8", "9", "0"]
COLORS_BGR = [[0, 0, 255], [0, 0, 0], [0, 0, 255], [0, 0, 0], [0, 0, 255], [0, 0, 0], [0, 0, 255], [0, 0, 0], [0, 0, 255], [0, 0, 0]]
COLORS = ["red", "black", "red", "black", "red", "black", "red", "black", "red", "black"]
THRESHOLD = 0.4
# Prepare model outputs
interpreter = make_interpreter(model)
interpreter.allocate_tensors()


# Font
font = ImageFont.truetype(r'/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)

# ID of the traffic light
tl = "TL01"

''' Operation mode from the dashboard
    standby:
        actuators off
        lane detection off
        traffic light detection off
        connected to the MQTT broker
        camera feed sent through TCP socket stream
    lanedetection:
        car speed 40
        lane detection on
        traffic light detection off
        connected to the MQTT broker
        camera feed sent through TCP socket stream
    tlviamqtt:
        car speed
            40 for green TL phase
            30 for yellow TL phase
            0 for red and redyellow phase
        lane detection on
        traffic light detection via mqtt
        connected to the MQTT broker
        camera feed sent through TCP socket stream
    tlviacnn:
        car speed
            40 for green TL phase
            30 for yellow TL phase
            0 for red and redyellow phase
        lane detection on
        traffic light detection via CNN
        connected to the MQTT broker
        camera feed sent through TCP socket stream
'''
mode = "standby"
lista = []
#numbers = [1,2, 3, 4, 5, 6, 7, 8, 9, 0]
#number = bytearray(numbers)

# Phase of the traffic light
phasemqtt = "red"
phasecnn = "red"

def sendframe(frame):
    framestream = cv2.resize(frame, (320, 240))
    # Send the frame via TCP
    ret, buffer = cv2.imencode('.jpg', framestream)
    b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(bytes(b64, 'utf-8'))

##############################################################

# MQTT publishing of smartcar values
def publish_mqtt(client, mode, speed, steer, campan, camtilt, tlphase):
    client.publish("SMARTCAR_status/mode", mode)
    client.publish("SMARTCAR_status/speed", speed)
    client.publish("SMARTCAR_status/steer", steer)
    client.publish("SMARTCAR_status/campan", campan)
    client.publish("SMARTCAR_status/camtilt", camtilt)
    client.publish("SMARTCAR_status/tlphase", tlphase)
    #client.publish("SMARTCAR_status/number", number)


def analyze_draw_objects(draw, objs):
    objects = []
    """Draws the bounding box and label for each object."""
    for obj in objs:
        if obj.id > len(CLASSES)-1:
            print("Unknown class id:", obj.id)
        else:
            bbox = obj.bbox
            draw.rectangle([(bbox.xmin, bbox.ymin), (bbox.xmax, bbox.ymax)],
                           outline=COLORS[obj.id], width=2)
            draw.text((bbox.xmin, bbox.ymin),
                      '%s (%d)' % (CLASSES[obj.id], obj.score*100),
                      fill=COLORS[obj.id])
            objects.append(CLASSES[obj.id])
            print(CLASSES[obj.id], obj.score*100)
            #print(str(bbox.xmin) + " " + str(bbox.xmax) + " " + str(bbox.ymin) + " " + str(bbox.ymax) + " Area of rectangle is " + str((bbox.xmax-bbox.xmin)*(bbox.ymax-bbox.ymin)))
            #print('%d\n%s\n%.2f' % (obj.id, CLASSES[obj.id], obj.score))
    return objects
    
def publish_mqtt_number(client, numbers):
    if len(numbers) == 0:
      numero = "no numbers"
    else:
      numero = int(numbers[0])
    client.publish("SMARTCAR_status/number", numero)

# MQTT receive callback
def on_message(client, userdata, message):
    
    global mode, phasemqttn
    topic_str = message.topic
    payload_str = message.payload.decode('ASCII')
    print(f"Received: topic={topic_str}  payload={payload_str}")
    print(type(payload_str))
    if topic_str == "SMARTCAR_control/mode":
        if payload_str == "standby":
            mode = "standby"
        elif payload_str == "lanedetection":
            mode = "lanedetection"
        elif payload_str == "tlviamqtt":
            mode = "tlviamqtt"
        elif payload_str == "start_delivery":
            mode = "start_delivery"
    if topic_str == tl:
        phasemqtt = payload_str
    '''    
    if topic_str == "SMARTCAR_delivery_data":
        order = json.loads(payload_str)
        print('Juanma chhupala')
        print(order)
        email = order['Email']
        num = order['Number']
        print(type(num))
        name = order['Name']
        ord = [email, num, name]
        lista.add(ord)'''
    if topic_str == "SMARTCAR_delivery_data":
        em = ".com"
        a = "@"
        if em in payload_str and a in payload_str and payload_str[-1] == 'm':
          partes = payload_str.split(',')
          partes_sin_espacios = [parte.strip() for parte in partes]
          name = partes_sin_espacios[0]
          number = partes_sin_espacios[1]
          email = partes_sin_espacios[2]
          l = [name, number, email]
          lista.append(l)
          print(lista)
      
      
        

def send_email(reci):
    subject = "Your package has arrived!"
    body = "Go take your package"
    sender = "pictamazon@gmail.com"
    recipient = reci
    password = "fyzbpfchzxyrynse"
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipient)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(sender, password)
       smtp_server.sendmail(sender, recipient, msg.as_string())
    print("Message sent!")
    
    
def main():
    global phasecnn
    # MQTT connection
    client = mqtt.Client()
    client.connect("localhost", 1883, 60)
    client.on_message = on_message
    client.subscribe("SMARTCAR_control/mode")
    client.subscribe("SMARTCAR_delivery_data")
    client.subscribe("SMARTCAR_status/number")
    client.subscribe(tl)
    client.loop_start()
    # SmartCar object without using the local camera and control window
    sc = smartcar.SmartCar(use_ultrasonic = True, use_local_window = False)
    try:
        while not sc.quit:
            phase2send = "off"
            # receive camera image and ultrasonic distance 
            sc.handle_sensors()
            # mode lanedetection
            if mode == "lanedetection":
                if sc.speed < 40:
                    sc.speed += 1
                # Call routines for driving the car
                sc.lane_detection()
                sc.user_command()
                sc.handle_actuators()
                sc.handle_window()
                sendframe(sc.frame)
            # mode tlviamqtt
            elif mode == "tlviamqtt":
                # Set speed according traffic light phase
                if phasemqtt == "red":
                    sc.speed = 0
                elif phasemqtt == "redyellow":
                    sc.speed = 0
                elif phasemqtt == "yellow":
                    sc.speed = 30
                elif phasemqtt == "green":
                    sc.speed = 40
                # Call routines for driving the car
                sc.lane_detection()
                sc.user_command()
                sc.handle_actuators()
                sc.handle_window()
                sendframe(sc.frame)
                phase2send = phasemqtt
            # mode tlviacnn
            elif mode == "start_delivery":
                # Convert to RGB color space
                image = Image.fromarray(cv2.cvtColor(sc.frame, cv2.COLOR_BGR2RGB))
                # Create a Draw object for drawing rectangle around the detected objects
                draw = ImageDraw.Draw(image)
                # Detect objects
                _, scale = common.set_resized_input(
                    interpreter, image.size, lambda size: image.resize(size, Image.ANTIALIAS))
                interpreter.invoke()
                objs = detect.get_objects(interpreter, THRESHOLD, scale)
                # Draw image and additional info
                if objs != None:
                    objects = analyze_draw_objects(draw, objs)
                frameout = numpy.array(image)
                sc.frame = cv2.cvtColor(frameout, cv2.COLOR_RGB2BGR)
                # Define the TL state with a certain priority for safety reasons
                phasecnn = "off"
                sc.speed = 40
                publish_mqtt_number(client, objects)
                if len(lista) == 0:
                    sc.speed = 0
                    num = None
                    print('lista vacia')
                else:
                    print('nuevo pedido')
                    order = lista[len(lista)-1]
                    email = order[2]
                    num = order[1]
                    name = order[0]
                    print('objetos')
                    print(objects)
                if num in objects and num != None:
                    
                    send_email(email)
                    lista.remove(order)
                    print('nueva lista: ')
                    print(lista)
                # Call routines for driving the car
                sc.lane_detection()
                sc.user_command()
                sc.handle_actuators()
                sc.handle_window()
                sendframe(sc.frame)
                phase2send = phasecnn
                sc.speed = 0
            # mode standby
            else:
                sc.speed = 0
                sc.p_part = 0
                sc.i_part = 0
                sc.d_part = 0
                sc.handle_actuators()
                sc.handle_window()
                sendframe(sc.frame)
            # Publish the current values of the SmartCar
            publish_mqtt(client, mode, sc.speed, sc.steer, sc.campan, sc.camtilt, phase2send)
            
    finally:
        # Clean up the SmartCar object
        sc = None
        # Disconnect MQTT
        client.loop_stop()
        client.unsubscribe(tl)
        client.unsubscribe("SMARTCAR_control/mode")
        client.unsubscribe("SMARTCAR_delivery_data")
        client.unsubscribe("SMARTCAR_status/number")
        client.disconnect()

if __name__ == "__main__":
    main()
