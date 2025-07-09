# VirtualFencingTechnology-for-RotationalGrazing

## 设计思路
在Preliminary_Report.docx中已经给出了示意图。  
### 1. Compute Layer - Edge Gateway
Edge Gateway控制两个东西：（1）sms消息发送，（2）Buzzer控制  
#### （1）sms消息发送（需要天线，合理的4G sim）
通过sim卡和内置的quick function实现  
步骤：   
* Gateway-Edge Computing-Cloud内建立listen Broker的app  
  Broker：10.166.179.5，1883
* 写sms的监听以及发送的quick function（测试阶段先用 mqttX 去模拟发送警报payload）
#### （2）Buzzer控制（IR302 pyModbus）  
* pass
    