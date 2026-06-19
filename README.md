# Drone-Wast-Detection 
Ziel ist eine Drohne die mit der Kamera ein Video macht. Dieses wird nach der Landung von einer KI analysiert und die Koordinaten des Mülls werden auf einer Karte makiert. 
Dadurch soll eine effizientere Sammlun des Mülls auf dem entsprechenden Gelände gewährleistet werden. 

## Hardware 
- DJI mini 3 Pro

## Funktionsweise 
1. Drohne fliegt über einen Bereich und macht ein Video
2. Yolov8n analysiert das Video un gibt Timestamps zurück, zu denen Müll gefunden wurde.
3. Die Timestamps werden an ein Programm gegeben, das über die dazugehörige SRT-Datei die Koordinaten zu den entsprechenden Zeitpunkten zurückgibt.
4. Diese Koordinaten werden über Folium auf einer Karte makiert



