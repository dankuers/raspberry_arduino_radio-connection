#include "Arduino.h"
#include <printf.h>
#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <avr/sleep.h>
#include <avr/power.h>

//RPi and Arduino address:
const char* Ardu_pointer = "0xF3ED100001";
unsigned long long Ardu = 0xF3ED100001;
unsigned long long RPi = 0xF3ED000001;
const uint64_t pipes[2] = { RPi, Ardu };

//CE and CSN pins:
int CE = 2;
int CSN = 3;

//Analog Voltage Measurement Pin and Resistor resistance in Ohm:
int analog_voltage_pin = A0;
float resistor1 = 1000;
float resistor2 = 10000;

//Sleepy device (0 = no; 1 = yes):
bool i_feel_sleepy = 0;

//Energyconsumption:
//0 is RF24_PA_MIN (-18dBm)
//1 is RF24_PA_LOW (-12dBm)
//2 is RF24_PA_HIGH (-6dBm)
//3 is RF24_PA_MAX (0dBm)
int energyconsumption = 1;

//Debugging 0 = no, 1 = yes
int printradiodetails = 0;

RF24 radio(CE, CSN);

// Sleep declarations:
typedef enum { wdt_16ms = 0, wdt_32ms, wdt_64ms, wdt_128ms, wdt_250ms, wdt_500ms, wdt_1s, wdt_2s, wdt_4s, wdt_8s } wdt_prescalar_e;
void do_sleep(void);
const short sleep_cycles_per_transmission = 4;
volatile short sleep_cycles_remaining = sleep_cycles_per_transmission;

bool address_check = false;
long pin_num;

void setup()
{

	Serial.begin(115200);
	if ( printradiodetails )
	{
		printf_begin();
	}

	radio.begin();

	switch ( energyconsumption )
	{
	case 0:
		radio.setPALevel(RF24_PA_MIN);
	break;
	case 1:
		radio.setPALevel(RF24_PA_LOW);
	break;
	case 2:
		radio.setPALevel(RF24_PA_HIGH);
	break;
	case 3:
		radio.setPALevel(RF24_PA_MAX);
	break;
	}

	radio.openWritingPipe(pipes[1]);
	radio.openReadingPipe(1, pipes[0]);
	radio.startListening();

	if ( printradiodetails )
	{
		radio.printDetails();
	}
}

void loop()
{

	if ( radio.available() )
	{

		char rec_data[32];

		while ( radio.available() )
		{
			radio.read( &rec_data, sizeof(rec_data) );
		}

		radio.stopListening();
		long cmd_value = atol(rec_data);

		if(strcmp(rec_data, Ardu_pointer) == 0)
		{
			address_check = true;
		}
		if ( (cmd_value < 0) && (address_check == true))
		{
			pin_num = -1 * cmd_value;
		}

		if ( (cmd_value >= 0) && (address_check == true) && (pin_num != 0))
		{

			if ( cmd_value >= 0 && cmd_value <= 255 )
			{

				// ------------------------------------- PWM OUTPUT -----------------------------------------

				Serial.print("Cmd: ");
				Serial.println(rec_data);
				radio.write( &rec_data, sizeof(rec_data) );
				Serial.print("Pin: ");
				Serial.println(pin_num);
				Serial.print("Address: ");
				Serial.println(Ardu_pointer);
				pin_num = 0;
				address_check = false;

			}
			else
			{

				// ---------------------------------- OTHER COMMANDS --------------------------------------
				if ( cmd_value == 256)
				{

					float analogval = analogRead(analog_voltage_pin);
					delayMicroseconds(250);
					float sen_data_float = (analogval / 1024 * 5) * (( resistor2 + resistor1 ) / resistor1);
					radio.write( &sen_data_float, sizeof(float) );

				}

				if ( cmd_value == 285)
				{

					Serial.print("Cmd: ");
					Serial.println(rec_data);

				}
			}
		}
		radio.startListening();
	}

	else

	{

		if ( i_feel_sleepy )
		{

			do_sleep();

		}
	}
}

void wakeUp()
{
	sleep_disable();
}

ISR(WDT_vect)
{
	//--sleep_cycles_remaining;
	Serial.println(F("WDT"));
}

void do_sleep(void)
{
	set_sleep_mode(SLEEP_MODE_PWR_DOWN); // sleep mode is set here
	sleep_enable();
	attachInterrupt(0,wakeUp,LOW);
	WDTCSR |= _BV(WDIE);
	sleep_mode();                        // System sleeps here
									   // The WDT_vect interrupt wakes the MCU from here
	sleep_disable();                     // System continues execution here when watchdog timed out
	detachInterrupt(0);
	WDTCSR &= ~_BV(WDIE);
}
