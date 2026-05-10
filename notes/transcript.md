# Transcript — BMW ZF 8HP Project 03: Aux 12V Pump Running At Last

Source: https://www.youtube.com/watch?v=89P2md4vqlg
Channel: Damien Maguire (openinverter)

Hello folks, welcome back to your most anticipated pump of doom update. Good news, pump of doom is now running. Let's go take a look. So, that only took nine days and in the end a lot of assistance from a very kind person. Now, the way with the pump running we can make some hydraulic pressure from a standstill, which is what we want.

So, can now turn our attention to the TCU or the TCM, whichever you prefer to to call it. Now, in the the little bit of in the AHP swapping land there's kind of two ways that they seem to do this. One is to run with the existing TCM, so there's a circuit in there. And they kind of do some secret handshake stuff and basically get it to run as if it were in the parent vehicle. And the second way is you cut this can open and replace the electronics in there with a board like this one.

This is just one I made up. It's kind of based on this one. Let me get that out of here. This one also comes with this kind of a kind of a nifty cover. And it's basically like that.

So that board goes inside there. And what that basically does is it connects all of the valves and things like the speed sensors and that directly to the external connector. So you can then control the valves with an external control box. Um and that was the way that I was going to go, to be honest. I was just going to I'd have to change the design of this board cuz this doesn't have the LIN connection, for example, for the pump.

But other than that, it's fine. so that's the way I was going to go. But I've been, obviously cuz I've been working on the LIN and the pump, I was having some thoughts. And so I want to run this past you folks and see what you think. Maybe there's kind of a forward option here.

So I'm thinking, rather than having a big kind of, you know, you have a board you put in here and then you have your external controller and harnesses and all that good stuff. Uh what if instead, we actually designed our open inverter TCM to go on that board. Uh we put our STM32, little power supply, support circuitry on a valve driver chip, which I have found. It's uh by Maxim. It's a very small chip, but it can literally drive all the valves from a single part.

And we literally put a CAN transceiver on that, a LIN transceiver to talk to the pump if you're using a hybrid one. And then we basically put this put the this board in there, in place of the existing TCM. And then um we can put this back into the gearbox and then we just give it ground 12 volts, CAN high, and CAN low low and we can you know, connect our web interface, we can send commands to it, we can send software updates and all that kind of thing. So, that's where I'm thinking of going, folks, because even a board like that, we can easily make six-layer now with JLC. Um so, it would be well feasible, I think, to do a a kind of a hybrid of the two, if you don't mind the pun.

So, we push a new TCM inside the TCM and then control that via CAN externally. So, that's kind of where my thoughts are at the minute, folks. Uh let me know what you think in the comments, please. So, we'd have a board like that, pretty much that size, um but we'd have our components on on here for our STM32-based TCM. So, that's about it.

As always, don't forget to dislike this garbage. Um don't subscribe. If you are subscribed, unsubscribe. so, you don't have to be exposed to this kind of nonsense any further. Uh so, I'm going to go ahead in the next episode, I'll get the CAN open on that uh TCM that I have there on the bench.

I will start kind of working out what pins we need to have on here and how it would kind of work out. But, I think a little board that size with a 32F1, CAN transceiver, LIN transceiver, a little power supply, and one of those Maxim valve driver chips would work quite well. So, don't know. We'll see what we can do. Anyway, I need to be something different.

There you go. All right, folks. That's enough of me talking nonsense.

