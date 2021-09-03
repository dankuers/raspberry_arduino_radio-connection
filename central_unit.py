from __future__ import print_function
from RF24 import *
import time
import MySQLdb

# 0-255 Light
# 256 Voltage
# 1000-1999 Temperature
# 2000-2999 Humidity
# 3000-3999 Pressure
# 4000-19999 Miscellaneous

# ------------------- Einstellbereich -----------------------------------

# RPi B
# Setup for GPIO 15 CE and CE1 CSN with SPI Speed @ 8Mhz
radio = RF24(RPI_V2_GPIO_P1_15, BCM2835_SPI_CS0, BCM2835_SPI_SPEED_8MHZ)
pipes = [0xF3ED000001]

# Energyconsumption:
# 0 is RF24_PA_MIN (-18dBm)
# 1 is RF24_PA_LOW (-12dBm)
# 2 is RF24_PA_HIGH (-6dBm)
# 3 is RF24_PA_MAX (0dBm)
energyconsumption = 1

# Debugging 0 = no, 1 = yes
printradiodetails = 0

# Time to wait for a response from an Arduino:
responsewaittime = 100
writingdelay = 10


# --------------------------------------------------------------------------

millis = lambda: int(round(time.time() * 1000))

def delay(milliseconds):
    taketime = millis()
    continuescript = False
    while not continuescript:
        if(millis() - taketime) > milliseconds:
            continuescript = True
    continuescript = False
    return

def sendstuff(device_id, send_cmd):

    curs.execute("SELECT arduino_id FROM arduino_id_to_arduino_pin WHERE device_id=%s" % device_id)
    rows = curs.fetchone()
    grab_arduino_id = rows[0]
    curs.execute("SELECT arduino_pin FROM arduino_id_to_arduino_pin WHERE device_id=%s" % device_id)
    rows = curs.fetchone()
    a_pin = rows[0]
    curs.execute("SELECT address FROM addresses WHERE rpi_arduino_id=%s AND rpi_0_arduino_1=%s" % (grab_arduino_id, 1))
    rows = curs.fetchone()
    receiver = rows[0]

    # Send address so the addressed Arduino knows its the supposed receiver
    senderror = False
    bytes_send_cmd = bytes(send_cmd)
    bytes_a_pin = bytes(-1*a_pin)
    bytes_address = bytes(receiver)
    radio.openWritingPipe(pipes[0])
    radio.openReadingPipe(1, int(receiver, 16))
    if printradiodetails:
        radio.printDetails()
    radio.stopListening()
    if not radio.write(bytes_address):
        senderror = True
        print("Addresserror")
    delay(writingdelay)

    # Send pin number to Arduino so it knows which pin it has got to use
    if not radio.write(bytes_a_pin):
        senderror = True
        print("Pinerror")
    delay(writingdelay)

    # Send command to Arduino
    if not radio.write(bytes_send_cmd):
        print("Cmderror")
        senderror = True

    # Receiving the Arduinos response
    radio.startListening()
    taketime = millis()
    continuescript = False
    while (not radio.available()) and (not continuescript):
        if (millis()-taketime) > responsewaittime:
            continuescript = True
    if continuescript:
        senderror = True
    else:
        print("There's smt available...")
        while radio.available():
            ba = radio.read(32)
            print("I do read smt")
            
        # Loop through the bytearray and count
        count = 0
        for x in range(32):
            if not ba[x] == 0:
                count += 1
        print("I did count smt: %s" % count)
            
        recv_answer = ''.join(chr(ba[x]) for x in range(count))
        print("The received answer, joined: %s" % recv_answer)
        
        insert_value_history(device_id, recv_answer, send_cmd)
        continuescript = True
        senderror = False
        
    continuescript = False
    return senderror

def insert_value_history(device_id, val, func_id):
    timerightnow = round(time.time())
    if (func_id >= 0) and (func_id <= 255):
        print("Inserting...")
        curs.execute("INSERT INTO values_light_history VALUES (%s, %s, %s)" % (device_id, val, timerightnow))
    if func_id == 256:
        curs.execute("INSERT INTO values_voltage_history VALUES (%s, %s, %s)" % (device_id, val, timerightnow))
    if (func_id >= 1000) and (func_id <= 1999):
        curs.execute("INSERT INTO values_temp_history VALUES (%s, %s, %s)" % (device_id, val, timerightnow))
    if (func_id >= 2000) and (func_id <= 2999):
        curs.execute("INSERT INTO values_humidity_history VALUES (%s, %s, %s)" % (device_id, val, timerightnow))
    if (func_id >= 3000) and (func_id <= 3999):
        curs.execute("INSERT INTO values_pressure_history VALUES (%s, %s, %s)" % (device_id, val, timerightnow))
    if (func_id >= 4000) and (func_id <= 19999):
        curs.execute("SELECT function_type FROM device_function_type WHERE device_id=%s" % device_id)
        rows = curs.fetchone()
        f_type = rows[0]
        curs.execute("INSERT INTO values_misc_history VALUES (%s, %s, %s, %s)" % (device_id, val, timerightnow, f_type))
    db.commit()
    return

def energylevel(elevel):
        switcher = {
                0: lambda: radio.setPALevel(RF24_PA_MIN),
                1: lambda: radio.setPALevel(RF24_PA_LOW),
                2: lambda: radio.setPALevel(RF24_PA_HIGH),
                3: lambda: radio.setPALevel(RF24_PA_MAX),
        }
        energylvl = switcher.get(elevel, lambda: None)
        return energylvl()


# --------------------------------------------------------------------------

radio.begin()

energylevel(energyconsumption)

while 1:

    db = MySQLdb.connect(host='localhost', user='root', passwd='ichbindoof123', db='usr_web136_2')
    curs = db.cursor()

    curs.execute("SELECT * FROM input")
    for row in curs:
        grab_function_id = row[0]
        grab_device_id = row[1]
        if sendstuff(grab_device_id, grab_function_id) == False:
            curs.execute("""DELETE FROM input WHERE function_id=%s AND device_id=%s LIMIT 1 
            """ % (grab_function_id, grab_device_id))
            print("Success")
            db.commit()
        else:
            time_error = round(time.time())
            print("Error")
            # curs.execute("INSERT INTO error_history VALUES (%s, %s, 'input', %s)" % (grab_device_id, grab_function_id, time_error))
            # db.commit()
           
    curs.execute("SELECT * FROM time_daily_repetitive")
    for row in curs:
        grab_device_id = row[0]
        grab_function_id = row[1]
        grab_point_of_time = row[2]
        done_this_week = row[3]
        timething = time.localtime()
        minute_of_the_week = timething[6]*1440 + timething[3]*60 + timething[4]
        if grab_point_of_time == minute_of_the_week and done_this_week == 0:
            sendstuff(grab_device_id, grab_function_id)
            curs.execute("""UPDATE time_daily_repetitive SET done_this_week=1 WHERE device_id=%s AND function_id=%s AND
            point_of_time=%s AND done_this_week=0 LIMIT 1""" % (grab_device_id, grab_function_id, grab_point_of_time))
            db.commit()
        elif grab_point_of_time < minute_of_the_week and done_this_week == 1:
            curs.execute("""UPDATE time_daily_repetitive SET done_this_week=0 WHERE device_id=%s AND function_id=%s AND
            point_of_time=%s AND done_this_week=1 LIMIT 1""" % (grab_device_id, grab_function_id, grab_point_of_time))
            db.commit()

    curs.execute("SELECT * FROM time_single_events")
    for row in curs:
        grab_device_id = row[0]
        grab_function_id = row[1]
        grab_year = row[2]
        grab_month = row[3]
        grab_day = row[4]
        grab_hour = row[5]
        grab_minute = row[6]
        point_of_time = round((time.mktime((grab_year, grab_month, grab_day, grab_hour, grab_minute, 0, 0, 0, -1)))/60)
        if point_of_time == round(time.time()/60):
            sendstuff(grab_device_id, grab_function_id)
            curs.execute("""DELETE FROM time_single_events WHERE device_id=%s AND function_id=%s AND year=%s AND
             month=%s AND day=%s AND hour=%s AND min=%s LIMIT 1
             """ % (grab_device_id, grab_function_id, grab_year, grab_month, grab_day, grab_hour, grab_minute))
            db.commit()

    curs.execute("SELECT * FROM time_updaterate")
    for row in curs:
        grab_device_id = row[0]
        grab_function_id = row[1]
        grab_interval_seconds = row[2]
        grab_last_update = row[3]
        timerightnow = round(time.time())
        if (grab_last_update + grab_interval_seconds) < timerightnow:
            sendstuff(grab_device_id, grab_function_id)
            curs.execute("""UPDATE time_updaterate SET last_update=%s WHERE device_id=%s AND function_id=%s AND
            interval_seconds=%s AND last_update=%s LIMIT 1
            """ % (timerightnow, grab_device_id, grab_function_id, grab_interval_seconds, grab_last_update))
            db.commit()

    db.close()