from __future__ import print_function

import wiiuse
import mido
import sys, time, os

nmotes = 1

class WiiMIDI():
    ids = ["wiimote", "nunchuk"] # to identify which controller is doing what
    # 0 is wiimote, 1 is nunchuk

    currentnote = 60
    noteon = []
    velocity = []
    notemod = "none" # sharp or flat
    pitchbend = 0
    octave = 4
    ch = 0

    pitchmod = 2048
    deadthres = 0.1 # dead zone for joystick
    deadbendthres = 20 # dead zone for roll

    hit_start = None
    hit_vel = 0.0
    hit_last = None
    hit_lastvel = 0.0
    hit_limit = 0.1 # like a threshold that affects when an impact is considered an impact, higher means harder impact
    hit_scale = 250.0

    rumble_on_impact = True # only the wiimote has rumble though but we'll see

    third = False # major is 4, minor 3
    fifth = False # perfect is 7
    seventh = False # major is 11, minor 10

    port = mido.open_output('Port Name')

    scalepos = { # first numbers will be different if negative angle
        0: 0,
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        6: 6,
        7: 7,
    } # A, B, C, D, E, F, G, A

    def end(self, id):
        for i in range(len(self.noteon)-1,-1,-1):
            msg = mido.Message('note_off', channel=self.ch, note=self.noteon.pop(i).note)
            self.port.send(msg)
        pass

    def handle_joystick(self, id, nc):
        # add dead zone in middle, if amplitude is enough
        if abs(nc.js.mag) > self.deadthres:
            self.currentnote = self.octave*12+self.scalepos[int(45 * round(float(nc.js.ang)/45))]
        pass

    def check_hit(self, id, pitch):
        if self.hit_start is not None:
            self.hit_vel = pitch - self.hit_last
            if self.hit_vel + self.hit_limit < self.hit_lastvel:
                force = min(127, int(self.hit_last*self.hit_scale))
                self.handle_hit(id, force)
        else:
            self.hit_start = pitch
        self.hit_last = pitch
        self.hit_lastvel = self.hit_vel
        pass
    def handle_hit(self, id, force):
        # check notemod and currentnote and send noteon, add to noteon array
        # turn on rumble if enabled
        realnote = self.currentnote
        if self.notemod == "sharp" and self.currentnote < 127:
            realnote += 1
        elif self.notemod == "flat" and self.currentnote > 0:
            realnote -= 1
        msg = mido.Message('note_on', channel=ch, note=self.currentnote, velocity=force)
        self.noteon.append(msg)
        self.port.send(msg)
        if self.rumble_on_impact:
            pass # probably make a rumble function that is threaded separately
        pass

    # make pitchbend have a resettable center
    def check_pitchbend(self, id, roll): # no yaw but we need to check what we can do
        # add dead zone in middle so not accident
        if roll > self.deadbendthres:
            self.handle_pitchbend(id, roll-self.deadbendthres)
        elif roll < -1*self.deadbendthres:
            self.handle_pitchbend(id, roll+self.deadbendthres)
        pass
    def handle_pitchbend(self, id, val):
        # send pitch bend multiplied by constant modifier such that default roll
        msg = mido.Message('pitchwheel', channel=self.ch, pitch=int(val/180)*self.pitchmod)
        self.port.send(msg)
        pass

    def handle_event(self, wmp):
        wm = wmp[0]
        print('--- EVENT [Wiimote ID %i] ---' % wm.unid)

        if wm.btns:
            for name, b in wiiuse.button.items():
                if wiiuse.is_pressed(wm, b):
                    print(name,'pressed')

            if wiiuse.is_just_pressed(wm, wiiuse.button['-']):
                wiiuse.motion_sensing(wmp, 0)
            if wiiuse.is_just_pressed(wm, wiiuse.button['+']):
                wiiuse.motion_sensing(wmp, 1)
            if wiiuse.is_just_pressed(wm, wiiuse.button['B']):
                wiiuse.toggle_rumble(wmp)
            if wiiuse.is_just_pressed(wm, wiiuse.button['Up']):
                wiiuse.set_ir(wmp, 1)
            if wiiuse.is_just_pressed(wm, wiiuse.button['Down']):
                wiiuse.set_ir(wmp, 0)
        
        if wiiuse.using_acc(wm):
            print('roll  = %f' % wm.orient.roll)
            print('pitch = %f' % wm.orient.pitch)
            print('yaw   = %f' % wm.orient.yaw)
        
        #if wiiuse.using_ir(wm):
        #    for i in range(4):
        #        if wm.ir.dot[i].visible:
        #            print 'IR source %i: (%u, %u)' % (i, wm.ir.dot[i].x, wm.ir.dot[i].y)
        #    print 'IR cursor: (%u, %u)' % (wm.ir.x, wm.ir.y)
        #    print 'IR z distance: %f' % wm.ir.z
            
        if wm.exp.type == wiiuse.EXP_NUNCHUK:
            nc = wm.exp.u.nunchuk

            if abs(nc.js.mag) < self.deadthres:
                self.end(self.ids[1])
            
            for name,b in wiiuse.nunchuk_button.items():
                if wiiuse.is_pressed(nc, b):
                    print('Nunchuk: %s is pressed' % name)

            print('nunchuk roll  = %f' % nc.orient.roll)
            print('nunchuk pitch = %f' % nc.orient.pitch)
            print('nunchuk yaw   = %f' % nc.orient.yaw)
            print('nunchuk joystick angle:     %f' % nc.js.ang)
            print('nunchuk joystick magnitude: %f' % nc.js.mag)


    def handle_ctrl_status(self, wmp, attachment, speaker, ir, led, battery_level):
        wm = wmp[0]
        print('--- Controller Status [wiimote id %i] ---' % wm.unid)
        print('attachment', attachment)
        print('speaker', speaker)
        print('ir', ir)
        print('leds', led[0], led[1], led[2], led[3])
        print('battery', battery_level)

def main():
    if os.name != 'nt': print('Press 1 & 2 to continue')

    wiimotes = wiiuse.init(nmotes)

    found = wiiuse.find(wiimotes, nmotes, 5)
    if not found:
        print('No Wii remote found, exiting with error code 1...')
        sys.exit(1)

    connected = wiiuse.connect(wiimotes, nmotes)
    if connected:
        print('Connected to %i Wii remote(s) (of %i found).' % (connected, found))
    else:
        print('Failed to connect to any Wii remote.')
        sys.exit(1)

    for i in range(nmotes):
        wiiuse.set_leds(wiimotes[i], wiiuse.LED[i])
        wiiuse.status(wiimotes[0])
        #wiiuse.set_ir(wiimotes[0], 1)
        #wiiuse.set_ir_vres(wiimotes[i], 1000, 1000)

    wm = WiiMIDI()

    try:
        rum = 1
        while True:
            r = wiiuse.poll(wiimotes, nmotes)
            if r != 0:
                wm.handle_event(wiimotes[0])
    except KeyboardInterrupt:
        for i in range(nmotes):
            wiiuse.set_leds(wiimotes[i], 0)
            wiiuse.rumble(wiimotes[i], 0)
            wiiuse.disconnect(wiimotes[i])

    print("Ended connection")

if __name__ == "__main__":
    main()