clear all 
close all

obj = SKAAPclient();
obj = obj.init();

[freq,mag,d] = obj.runMeasurement();
figure
plot(freq./1e06,mag)
xlabel('Frequency (MHz)')
ylabel('Magnitude (dB)')
grid on 
grid minor
title(string(d))