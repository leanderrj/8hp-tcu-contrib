# Transcript — BMW ZF 8HP Project 03: Aux 12V Pump Running At Last

Source: https://www.youtube.com/watch?v=89P2md4vqlg

**[00:00:02]** Hello folks, welcome back to your most

**[00:00:02]** anticipated pump of doom update. Good

**[00:00:06]** anticipated pump of doom update. Good

**[00:00:06]** news, pump of doom is now running.

**[00:00:09]** news, pump of doom is now running.

**[00:00:09]** Let's go take a look.

**[00:00:41]** So, that only took nine days

**[00:00:41]** and in the end

**[00:00:43]** and in the end

**[00:00:43]** a lot of assistance from a very kind

**[00:00:46]** a lot of assistance from a very kind

**[00:00:46]** person.

**[00:00:47]** person.

**[00:00:47]** Now,

**[00:00:49]** Now,

**[00:00:49]** the way with the pump running we can

**[00:00:50]** the way with the pump running we can

**[00:00:50]** make some hydraulic pressure from a

**[00:00:53]** make some hydraulic pressure from a

**[00:00:53]** standstill, which is what we want. So,

**[00:00:57]** standstill, which is what we want. So,

**[00:00:57]** can now turn our attention to the TCU or

**[00:00:59]** can now turn our attention to the TCU or

**[00:00:59]** the TCM, whichever you prefer to to call

**[00:01:03]** the TCM, whichever you prefer to to call

**[00:01:03]** it. Now, in the

**[00:01:05]** it. Now, in the

**[00:01:05]** the little bit of in the AHP swapping

**[00:01:09]** the little bit of in the AHP swapping

**[00:01:09]** land there's kind of two ways that they

**[00:01:11]** land there's kind of two ways that they

**[00:01:11]** seem to do this.

**[00:01:13]** seem to do this.

**[00:01:13]** One is to run with the existing TCM, so

**[00:01:17]** One is to run with the existing TCM, so

**[00:01:17]** there's a

**[00:01:18]** there's a

**[00:01:18]** circuit in there.

**[00:01:20]** circuit in there.

**[00:01:20]** And they kind of

**[00:01:23]** And they kind of

**[00:01:23]** do some secret handshake stuff and

**[00:01:26]** do some secret handshake stuff and

**[00:01:26]** basically get it to run as if it were in

**[00:01:30]** basically get it to run as if it were in

**[00:01:30]** the parent vehicle.

**[00:01:32]** the parent vehicle.

**[00:01:32]** And the second way is you cut this can

**[00:01:35]** And the second way is you cut this can

**[00:01:35]** open

**[00:01:36]** open

**[00:01:36]** and replace the electronics in there

**[00:01:39]** and replace the electronics in there

**[00:01:39]** with a board like this one. This is just

**[00:01:41]** with a board like this one. This is just

**[00:01:41]** one I

**[00:01:42]** one I

**[00:01:42]** made up. It's kind of based on this one.

**[00:01:47]** made up. It's kind of based on this one.

**[00:01:47]** Let me get that out of here.

**[00:01:49]** Let me get that out of here.

**[00:01:49]** This one also comes with this kind of a

**[00:01:53]** This one also comes with this kind of a

**[00:01:53]** kind of a nifty cover.

**[00:01:56]** kind of a nifty cover.

**[00:01:56]** And

**[00:01:57]** And

**[00:01:58]** it's basically like that.

**[00:02:00]** it's basically like that.

**[00:02:00]** So that board goes inside there.

**[00:02:02]** So that board goes inside there.

**[00:02:02]** And what that basically does is it

**[00:02:04]** And what that basically does is it

**[00:02:04]** connects all of the valves and things

**[00:02:07]** connects all of the valves and things

**[00:02:07]** like the speed sensors and that

**[00:02:10]** like the speed sensors and that

**[00:02:10]** directly to the external connector. So

**[00:02:14]** directly to the external connector. So

**[00:02:14]** you can then control the valves with an

**[00:02:17]** you can then control the valves with an

**[00:02:17]** external control box.

**[00:02:20]** external control box.

**[00:02:20]** Um

**[00:02:22]** Um

**[00:02:22]** and that was the way that I was going to

**[00:02:24]** and that was the way that I was going to

**[00:02:24]** go, to be honest. I was just going to

**[00:02:27]** go, to be honest. I was just going to

**[00:02:27]** I'd have to change the design of this

**[00:02:30]** I'd have to change the design of this

**[00:02:30]** board cuz this doesn't have the LIN

**[00:02:32]** board cuz this doesn't have the LIN

**[00:02:32]** connection, for example, for the pump.

**[00:02:35]** connection, for example, for the pump.

**[00:02:35]** But other than that, it's fine.

**[00:02:38]** But other than that, it's fine.

**[00:02:38]** Um

**[00:02:39]** Um

**[00:02:39]** so that's the way I was going to go.

**[00:02:43]** so that's the way I was going to go.

**[00:02:43]** But I've been, obviously cuz I've been

**[00:02:44]** But I've been, obviously cuz I've been

**[00:02:44]** working on the LIN and the pump, I was

**[00:02:47]** working on the LIN and the pump, I was

**[00:02:47]** having some thoughts. And so I want to

**[00:02:49]** having some thoughts. And so I want to

**[00:02:49]** run this past you folks and see what you

**[00:02:52]** run this past you folks and see what you

**[00:02:52]** think. Maybe there's kind of a forward

**[00:02:55]** think. Maybe there's kind of a forward

**[00:02:55]** option here.

**[00:02:57]** option here.

**[00:02:57]** So I'm thinking, rather than having

**[00:03:00]** So I'm thinking, rather than having

**[00:03:01]** a big kind of, you know, you have a

**[00:03:02]** a big kind of, you know, you have a

**[00:03:02]** board you put in here and then you have

**[00:03:04]** board you put in here and then you have

**[00:03:04]** your external controller and harnesses

**[00:03:07]** your external controller and harnesses

**[00:03:07]** and all that good stuff.

**[00:03:09]** and all that good stuff.

**[00:03:09]** Uh what if

**[00:03:11]** Uh what if

**[00:03:11]** instead, we actually designed our

**[00:03:16]** instead, we actually designed our

**[00:03:16]** open inverter TCM to go on that board.

**[00:03:19]** open inverter TCM to go on that board.

**[00:03:19]** Uh

**[00:03:20]** Uh

**[00:03:20]** we put our STM32, little power supply,

**[00:03:23]** we put our STM32, little power supply,

**[00:03:23]** support circuitry on a valve driver

**[00:03:26]** support circuitry on a valve driver

**[00:03:26]** chip, which I have found.

**[00:03:28]** chip, which I have found.

**[00:03:28]** It's uh by Maxim. It's a very small

**[00:03:31]** It's uh by Maxim. It's a very small

**[00:03:31]** chip, but it can literally drive all the

**[00:03:33]** chip, but it can literally drive all the

**[00:03:33]** valves from a single part.

**[00:03:35]** valves from a single part.

**[00:03:36]** And we literally put a CAN transceiver

**[00:03:38]** And we literally put a CAN transceiver

**[00:03:38]** on that, a LIN transceiver to talk to

**[00:03:40]** on that, a LIN transceiver to talk to

**[00:03:40]** the pump if you're

**[00:03:42]** the pump if you're

**[00:03:42]** using a hybrid one.

**[00:03:44]** using a hybrid one.

**[00:03:44]** And then we basically put this

**[00:03:47]** And then we basically put this

**[00:03:47]** put the this board in there, in place of

**[00:03:50]** put the this board in there, in place of

**[00:03:50]** the existing TCM.

**[00:03:52]** the existing TCM.

**[00:03:52]** And then

**[00:03:54]** And then

**[00:03:54]** um

**[00:03:55]** um

**[00:03:55]** we can put this back into the gearbox

**[00:03:57]** we can put this back into the gearbox

**[00:03:57]** and then we just give it

**[00:03:59]** and then we just give it

**[00:03:59]** ground 12 volts, CAN high, and CAN low

**[00:04:02]** ground 12 volts, CAN high, and CAN low

**[00:04:02]** low and we can

**[00:04:04]** low and we can

**[00:04:04]** you know, connect our web interface, we

**[00:04:06]** you know, connect our web interface, we

**[00:04:06]** can send commands to it, we can send

**[00:04:09]** can send commands to it, we can send

**[00:04:09]** software updates and all that kind of

**[00:04:11]** software updates and all that kind of

**[00:04:11]** thing. So, that's where I'm thinking of

**[00:04:14]** thing. So, that's where I'm thinking of

**[00:04:14]** going, folks, because

**[00:04:16]** going, folks, because

**[00:04:16]** even a board like that, we can easily

**[00:04:18]** even a board like that, we can easily

**[00:04:18]** make six-layer now with JLC.

**[00:04:22]** make six-layer now with JLC.

**[00:04:22]** Um so, it would be well feasible, I

**[00:04:25]** Um so, it would be well feasible, I

**[00:04:25]** think, to do a

**[00:04:29]** think, to do a

**[00:04:29]** a kind of a hybrid of the two, if you

**[00:04:31]** a kind of a hybrid of the two, if you

**[00:04:31]** don't mind the pun. So, we push a new

**[00:04:34]** don't mind the pun. So, we push a new

**[00:04:34]** TCM inside the TCM and then control that

**[00:04:38]** TCM inside the TCM and then control that

**[00:04:38]** via CAN externally.

**[00:04:42]** via CAN externally.

**[00:04:42]** So, that's kind of where my thoughts are

**[00:04:44]** So, that's kind of where my thoughts are

**[00:04:44]** at the minute, folks. Uh let me know

**[00:04:46]** at the minute, folks. Uh let me know

**[00:04:46]** what you think in the comments, please.

**[00:04:49]** what you think in the comments, please.

**[00:04:49]** So, we'd have a

**[00:04:51]** So, we'd have a

**[00:04:51]** board like that, pretty much that size,

**[00:04:54]** board like that, pretty much that size,

**[00:04:54]** um but we'd have our components on on

**[00:04:56]** um but we'd have our components on on

**[00:04:56]** here

**[00:04:58]** here

**[00:04:58]** for our STM32-based

**[00:05:00]** for our STM32-based

**[00:05:00]** TCM. So,

**[00:05:07]** that's about it. As always, don't forget

**[00:05:07]** to dislike this garbage.

**[00:05:10]** to dislike this garbage.

**[00:05:10]** Um don't subscribe. If you are

**[00:05:11]** Um don't subscribe. If you are

**[00:05:11]** subscribed, unsubscribe.

**[00:05:14]** subscribed, unsubscribe.

**[00:05:14]** Um

**[00:05:15]** Um

**[00:05:15]** so, you don't have to be exposed to this

**[00:05:17]** so, you don't have to be exposed to this

**[00:05:17]** kind of nonsense any further.

**[00:05:20]** kind of nonsense any further.

**[00:05:20]** Uh so, I'm going to go ahead in the next

**[00:05:22]** Uh so, I'm going to go ahead in the next

**[00:05:22]** episode, I'll get the CAN open on that

**[00:05:25]** episode, I'll get the CAN open on that

**[00:05:25]** uh TCM that I have there on the bench. I

**[00:05:29]** uh TCM that I have there on the bench. I

**[00:05:29]** will start kind of working out what pins

**[00:05:32]** will start kind of working out what pins

**[00:05:32]** we need to have on here and how it would

**[00:05:36]** we need to have on here and how it would

**[00:05:36]** kind of work out. But, I think a little

**[00:05:37]** kind of work out. But, I think a little

**[00:05:37]** board that size

**[00:05:40]** board that size

**[00:05:40]** with a 32F1,

**[00:05:43]** with a 32F1,

**[00:05:43]** CAN transceiver, LIN transceiver, a

**[00:05:45]** CAN transceiver, LIN transceiver, a

**[00:05:45]** little power supply, and one of those

**[00:05:47]** little power supply, and one of those

**[00:05:47]** Maxim

**[00:05:48]** Maxim

**[00:05:49]** valve driver chips

**[00:05:51]** valve driver chips

**[00:05:51]** would work quite well. So, don't know.

**[00:05:55]** would work quite well. So, don't know.

**[00:05:55]** We'll

**[00:05:56]** We'll

**[00:05:56]** see what we can do. Anyway, I need to be

**[00:05:58]** see what we can do. Anyway, I need to be

**[00:05:58]** something different.

**[00:06:00]** something different.

**[00:06:00]** There you go. All right, folks. That's

**[00:06:02]** There you go. All right, folks. That's

**[00:06:02]** enough of me talking nonsense.

