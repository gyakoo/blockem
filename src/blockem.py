#/usr/bin/env python

#Import Modules
import os, pygame, copy
import math, random
from pygame.locals import *
import threading

if not pygame.font : print "Warning, pygame 'font' module disabled!"
if not pygame.mixer: print "Warning, pygame 'sound' module disabled!"

# --------------------------------------------------------
# Clamping a number between min m and max M
# --------------------------------------------------------
def clamp(x,m,M):
    if   x < m : return m
    elif x > M : return M
    return x
    
GAME = None # Global GAME variable

# --------------------------------------------------------
# This thread in charge of rendering to pygame display
# --------------------------------------------------------
class DrawingThread(threading.Thread):    
    def __init__(self,game):        
        threading.Thread.__init__(self)
        self.game = game
        self.drawingbuff = []
        self.ended = False
        self.clock = pygame.time.Clock()
                
    def run(self):
        while not self.ended:
            self.clock.tick(60)
            self.game.SCREEN.fill((0,0,0))
            for a in self.drawingbuff:
                self.game.SCREEN.blit( a[1], a[2] )            
            pygame.display.flip() # pygame flip
    
    def flip(self,buff):
        self.drawingbuff = buff
        
# --------------------------------------------------------
# Main Game class
# --------------------------------------------------------
class GameClass:
    def __init__(self,name,resolution):
        self.clock = pygame.time.Clock()
        self.SCREENRECT= Rect(0, 0, resolution[0], resolution[1])
        self.IMAGECACHE, self.SOUNDCACHE, self.FONTCACHE = {}, {}, {}
        self.KEYPRESSED = None
        bestdepth = pygame.display.mode_ok(self.SCREENRECT.size, pygame.DOUBLEBUF, 32)
        self.SCREEN = pygame.display.set_mode(self.SCREENRECT.size, pygame.DOUBLEBUF, bestdepth)
        self.name = name
        pygame.display.set_caption(name)
        self.newactors = []
        self.actors = []
        self.drawingbuff, self.commandbuff = [], []
        self.atfps, self.nextSound = 0.0, 0.0
        self.drawingThread = DrawingThread(self)
        self.drawingThread.start()
        self.levels, self.curlevel = os.listdir ( "data/levels" ), 0
        self.curlevel = len(self.levels)-1
        #preloading
        self.loadSound("click")
        self.loadSound("xp")
        self.loadSound("bell")
        
    def nextLevel(self):
        return os.path.join("data/levels",self.levels[ self.curlevel%len(self.levels) ])
        
    def loadFont(self,fontname,size):
        if not pygame.font: return None
        key = (fontname,size)
        font = None
        if not self.FONTCACHE.has_key(key):
            path = "data/"+fontname
            font = pygame.font.Font(path, size)
            if font: self.FONTCACHE[key] = font
        else:
            font = self.FONTCACHE[ key ]
        return font
        
    def loadSound(self,name):
        fullname = "data/"+name #os.path.join('data', name)
        sound = None
        if not self.SOUNDCACHE.has_key(name):            
            try: 
                sound = pygame.mixer.Sound(fullname+".wav")
            except pygame.error, message:
                print 'Cannot load sound:', name
            if sound:
                self.SOUNDCACHE[name] = sound
        else:
            sound = self.SOUNDCACHE[name]
        return sound
    
    def loadImage(self,file, rotation = 0, flipx = False, flipy = False):
        key = (file, rotation, flipx, flipy)
        if not self.IMAGECACHE.has_key(key):
            path = "data/"+file #os.path.join('data', file)
            ext = ["", ".bmp", ".gif", ".png"]
            for e in ext:
                if os.path.exists(path + e):
                    path = path + e
                    break
            if rotation or flipx or flipy:
                img = self.loadImage(file)
            else:
                img = pygame.image.load(path).convert_alpha()
            if rotation:
                img = pygame.transform.rotate(img, rotation)
            if flipx or flipy:
                img = pygame.transform.flip(img, flipx, flipy)
            self.IMAGECACHE[key] = img
        return self.IMAGECACHE[key]
        
    def playSound(self,name,vol=1.0):
        if self.nextSound <= 0.0: # avoiding two very consecutive sounds
            sound = self.loadSound(name)
            sound.set_volume(vol)
            sound.play()
            self.nextSound = 0.1
        
    def destroy(self):
        self.drawingThread.ended = True
        self.drawingThread.join()
        
    def sendMessage(self,msg):
        for a in self.actors:
            a.sendMessage(msg)
        for a in self.newactors:
            a.sendMessage(msg)
            
    def addActor(self,a):
        self.newactors.append(a)
        
    def draw(self,cmd):
        self.commandbuff.append(cmd)       
    
    # return minimum collision object
    def collision(self,o,r):
        minor = 1e10
        collider = None
        for a in self.actors:
            if hasattr(a,"collidable") and a.collidable:
                if r.colliderect( a.rect ):
                    d = (o[0] - a.rect.centerx)*(o[0]-a.rect.centerx) + \
                        (o[1] - a.rect.centery)*(o[1]-a.rect.centery)
                    if d < minor:
                        minor = d
                        collider = a
        return collider
                
    def update(self,dt):
        # Update fps stats
        self.atfps += dt
        self.nextSound -= dt
        if self.atfps > 3.0:
            pygame.display.set_caption(self.name + " fps: " + str(int(self.clock.get_fps())) + \
                                " / " + str(int(self.drawingThread.clock.get_fps())))
            self.atfps = 0.0
        
        # Processing actors, and we remove those terminated
        for a in self.actors:
            if a.terminated:
                self.actors.remove(a)
            else:
                a.update(dt)
        
        # Adding new actors from incoming actors buffer
        if len(self.newactors)>0:
            self.actors += self.newactors
            self.newactors = []
        
        # Swapping buffers and notifying to rendering thread the new rendering commands
        self.drawingbuff, self.commandbuff = self.commandbuff, self.drawingbuff        
        self.drawingbuff.sort()
        self.drawingThread.flip( self.drawingbuff )
        self.commandbuff = []        

# --------------------------------------------------------
# Main Entity class (contains behaviors)
# --------------------------------------------------------
class Actor:    
    def __init__(self):
        self.terminated = False
        self.behaviors = []
        
    def addBehavior(self,beh):
        self.behaviors.insert( 0, beh )
        
    def sendMessage(self,msg):
        for b in self.behaviors:
            t = hasattr(b,"terminated") and b.terminated
            if hasattr(b,"message") and not t:
                b.message(msg)
            
    def update(self,dt):
        for b in self.behaviors:            
            if hasattr(b,"terminated") and b.terminated:
                self.behaviors.remove( b )
            elif hasattr(b,"update"): 
                b.update(dt)

# --------------------------------------------------------
# Draw a sprite. Actor acts like a sprite then.
# --------------------------------------------------------
class BhDrawing:
    def __init__(self,actor,img=None,pos=(),zord=0):
        self.actor = actor
        self.actor.zord = zord
        self.actor.visible = True
        self.actor.image = None
        self.actor.rect = None
        self.actor.x,self.actor.y = 0,0
        self.actor.imageName = ""
        if img != None:
            self.actor.imageName = img
            self.actor.image = GAME.loadImage(img)
            self.actor.rect = self.actor.image.get_rect()
            self.actor.x,self.actor.y = self.actor.rect.left, self.actor.rect.top
        if pos: 
            self.actor.x, self.actor.y = pos[0],pos[1]
            
    def update(self,dt):
        if self.actor.image != None and self.actor.visible:
            self.actor.rect.topleft = (self.actor.x, self.actor.y)
            GAME.draw( ( self.actor.zord, self.actor.image, self.actor.rect ) )

# --------------------------------------------------------
# 
# --------------------------------------------------------
class BhBrokenBlock:
    def __init__(self,actor):
        self.actor = actor
        self.actor.image = GAME.loadImage("bblock")
        self.actor.rect = self.actor.image.get_rect()
        
    def message(self,msg):
        if msg["msg"] == "collision":            
            vx,vy = msg["vec"]
            #if vx*vx + vy*vy > 750*750:
            self.actor.terminated = True
            GAME.sendMessage({"msg":"updatepoints","points":1})

# --------------------------------------------------------
# With this behav., the entity can collide 
# --------------------------------------------------------
class BhColliding:
    def __init__(self,actor,response=True):
        self.actor = actor
        self.actor.collidable = True
        self.actor.response = True

# --------------------------------------------------------
# 
# --------------------------------------------------------
class BhTurningBlock:
    def __init__(self,actor,step=2,ang=90,defang=0,pow=500):
        self.actor = actor        
        self.actor.response = False
        self.step, self.ang = step, ang
        self.nextTurn = step
        self.nextcoll = 0
        self.acumang = 0
        self.pow = pow
        self.savedimg = self.actor.image        
        if defang:
            self.acumang = defang
            self.turnTo(defang)
        
    def update(self,dt):
        self.nextcoll -= dt
        self.nextTurn -= dt
        if self.nextTurn <= 0.0:            
            self.acumang += self.ang
            self.nextTurn = self.step
            self.turnTo(self.acumang)
            
    def turnTo(self,ang):
        self.oldcenter = (self.actor.x+self.actor.rect.width/2, self.actor.y+self.actor.rect.height/2)
        self.actor.image = pygame.transform.rotozoom( self.savedimg, self.acumang, 1.0 )
        self.actor.rect = self.actor.image.get_rect()
        self.actor.x = self.oldcenter[0]-self.actor.rect.width/2
        self.actor.y = self.oldcenter[1]-self.actor.rect.height/2            
            
    def message(self,msg):
        if msg["msg"] == "collision" and self.nextcoll < 0.0:
            self.nextcoll = 0.2
            r = math.radians(self.acumang)
            c = self.actor.rect.center
            GAME.sendMessage( {"msg":"blastplayer","vec":( -math.sin(r),-math.cos(r)),
                               "pw":self.pow,"o":c} )
            
            
# --------------------------------------------------------
# 
# --------------------------------------------------------
class BhSleepingBlock:
    def __init__(self,actor):
        self.actor = actor
        self.next = 0.0
        self.actor.zord = 7
        
    def message(self,msg):
        if msg["msg"] == "collision":
            self.terminated = True
            self.actor.addBehavior( BhDeathBlock(self.actor,bt=0.5) )
            self.actor.addBehavior( BhChasingBlock(self.actor, msg["player"]) )
            self.actor.image = GAME.loadImage("pblock2")
            
    def update(self,dt):
        self.next -= dt
        if self.next <= 0.0:
            createTextAnim( "z", self.actor.x+self.actor.rect.width/2,\
                                 self.actor.y+self.actor.rect.height/2, 1.5, (0,0,255) )
            self.next = 3.0

# --------------------------------------------------------
# Chasing
# --------------------------------------------------------
class BhChasingBlock:
    def __init__(self,actor,player,wt=2.0,ct=2.0,n=-1,vel=38):
        self.actor = actor
        self.player = player
        self.waitTime, self.chaseTime = wt, ct
        self.vel = vel
        self.n = n+1
        self.changeState( "wait" )
        
    def changeState(self,st):
        self.state = st
        self.nextState = self.waitTime if st == "wait" else self.chaseTime
        if st == "chase":
            v = (self.player.x-self.actor.x,self.player.y-self.actor.y)
            l = math.sqrt(v[0]*v[0] + v[1]*v[1])
            self.chaseVec = (v[0]/l, v[1]/l)
            if self.n == 0 or l > 280.0:
                self.backToSleep()                
        else:
            self.n -= 1            
            
    def backToSleep(self):
        self.terminated = True
        self.actor.sendMessage( {"msg":"nodeath"} )
        self.actor.addBehavior( BhSleepingBlock(self.actor) )
        self.actor.image = GAME.loadImage("pblock")
        self.actor.rect = self.actor.image.get_rect()
        
    def update(self,dt):
        self.nextState -= dt
        if self.nextState <= 0.0:
            self.changeState( "wait" if self.state=="chase" else "chase" )
        else:
            if self.state == "chase":
                self.actor.x += self.chaseVec[0]*self.vel*dt
                self.actor.y += self.chaseVec[1]*self.vel*dt
    
    def message(self,msg):
        if msg["msg"] == "playerdie":
            self.backToSleep()
            
# --------------------------------------------------------
# Acts like a white block
# --------------------------------------------------------
class BhWhiteBlock:
    def __init__(self,actor):
        self.actor = actor
    def message( self, msg ):
        if msg["msg"] == "collision":
            self.terminated = True
            self.actor.sendMessage( {"msg":"turn2yellow"} )
            GAME.sendMessage({"msg":"updatepoints","points":1})
            GAME.sendMessage({"msg":"updateremains","remains":-1})
            self.actor.addBehavior( BhYellowBlock(self.actor) )

# --------------------------------------------------------
# Acts like a enemy block
# --------------------------------------------------------
class BhDeathBlock:
    def __init__(self,actor,blink=True,bt=1.0):
        self.actor = actor        
        if blink:
            self.actor.addBehavior( BhBlinking(actor,bt) )
        else:
            self.actor.blinking = False
        
    def message(self,msg):
        if not self.actor.blinking:
            if msg["msg"] == "collision":
                GAME.sendMessage( { "msg": "playerdie" } )
            elif msg["msg"] == "nodeath":
                self.terminated = True

# --------------------------------------------------------
# Acts like a yellow block
# --------------------------------------------------------
class BhYellowBlock:
    def __init__(self,actor,blink=True):
        self.actor = actor
        if blink:
            self.actor.addBehavior( BhBlinking(actor,0.8,0.04) )
        else:
            self.actor.blinking = False
        
    def message( self, msg ):
        if not self.actor.blinking and msg["msg"] == "collision":
            self.terminated = True
            self.actor.image = GAME.loadImage("rblock")
            self.actor.sendMessage( {"msg":"turn2death"} )
            GAME.sendMessage( {"msg":"updatepoints","points":-1} )
            self.actor.addBehavior( BhShaking(self.actor) )
            self.actor.addBehavior( BhDeathBlock(self.actor) )

# --------------------------------------------------------
# Blink behavior in a time
# --------------------------------------------------------
class BhBlinking:
    def __init__(self,actor,et=1.0,v=0.04):
        self.actor = actor
        self.enabledtime = et
        self.v = v
        self.at = v
        self.actor.blinking = True
    def update(self,dt):
        self.at -= dt
        if self.at <= 0.0:
            self.actor.visible = not self.actor.visible
            self.at = self.v
        self.enabledtime -= dt
        if self.enabledtime <= 0.0:
            self.actor.visible = True
            self.actor.blinking = False
            self.terminated = True

# --------------------------------------------------------
# Moves the block
# --------------------------------------------------------
class BhMoverBlock:
    def __init__(self,actor,vel=2.0,dist=64.0,dirx=1.0,diry=0.0):
        self.actor = actor
        self.at = 0.0
        self.dirx,self.diry = dirx,diry
        self.savedx,self.savedy = self.actor.x,self.actor.y
        self.vel, self.dist = vel, dist    
        self.actor.zord = 8
    def update(self,dt):
        self.actor.x = self.savedx + math.sin(self.at) * self.dist * self.dirx
        self.actor.y = self.savedy + math.cos(self.at) * self.dist * self.diry
        self.at += dt*self.vel
        
# --------------------------------------------------------
# Shakes the block
# --------------------------------------------------------
class BhShaking:
    def __init__(self,actor):
        self.actor = actor
        self.nextshake = random.randint(5,30)
        self.at = 0.0
        self.st = "waiting"
        self.dir = random.randint(0,1)
        
    def update(self,dt):   
        if self.st == "waiting":
            self.nextshake -= dt
            if self.nextshake <= 0.0:
                self.nextshake = random.randint(15,30)
                self.st = "shaking"
                self.saved = self.actor.x if self.dir == 0 else self.actor.y
        else:
            self.at += dt
            d = self.saved + math.sin(self.at*64.0)*4.0
            if self.dir == 0: self.actor.x = d
            else: self.actor.y = d
            if self.at > 0.5:
                self.st = "waiting"
                self.at = 0.0
                if self.dir == 0: self.actor.x = self.saved
                else: self.actor.y = self.saved
                self.dir = random.randint(0,1)
                
# --------------------------------------------------------
# Creates a points (+1, -1, -5 ...) animated sprite
# --------------------------------------------------------
class BhTextAnim:
    def __init__(self,actor,points,pos,dur=0.8,c=(255,255,255)):
        self.actor = actor
        self.font = GAME.loadFont("type_writer.ttf",10)
        txt,color = str(points), c
        if type(points) is int:
            if points<0 : color = (255,0,0)
            else        : txt, color = "+"+txt, (0,255,0)
                
        self.actor.image = self.font.render(txt,1,color)
        self.actor.rect = self.actor.image.get_rect()
        self.actor.x, self.actor.y = pos[0]-self.actor.rect.width/2, pos[1]-self.actor.rect.height/2
        self.time = dur
        
    def update(self,dt):
        self.time -= dt
        if self.time <= 0.0:
            self.actor.terminated = True
        else:
            self.actor.y -= 16 * dt
    
# --------------------------------------------------------
# Generic sprite animation (bounce and explosion)
# --------------------------------------------------------
class BhAnim:
    def __init__(self,actor,anim,n=6,period=0.01):
        self.actor = actor
        self.n = n
        self.period = period
        self.images = [GAME.loadImage(i) for i in [anim+str(j) for j in range(0,n)]]
        self.nextimg = self.period
        self.curimg = 0
        self.changeImage(self.curimg)
        
    def changeImage(self,ndx):
        cx,cy = self.actor.x+self.actor.rect.width/2, self.actor.y+self.actor.rect.height/2
        self.actor.image = self.images[ndx]
        self.actor.rect = self.actor.image.get_rect()
        self.actor.rect.center = (cx,cy)
        self.actor.x,self.actor.y = self.actor.rect.left, self.actor.rect.top
        
    def update(self,dt):
        self.nextimg -= dt
        if self.nextimg <= 0.0:
            self.nextimg = self.period
            self.curimg += 1
            if self.curimg == self.n:
                self.actor.terminated = True
            else:                
                self.changeImage( self.curimg )

# --------------------------------------------------------
# Changes the sprite every x seconds (gestures in blocks)
# --------------------------------------------------------
class BhGestureBlock:
    def __init__(self,actor,img0,img1,rt=(10,25),at=2.0):
        self.actor = actor
        self.rt,self.at = rt,at
        self.images = [ GAME.loadImage(img0), GAME.loadImage(img1) ]
        self.actor.image = self.images[0]
        self.state = "norm"
        self.nextimg = random.randint(rt[0],rt[1])
    
    def message(self,msg):
        if msg["msg"] == "turn2yellow":
            self.images = [ GAME.loadImage("yblock"), GAME.loadImage("yblock2") ]
            self.actor.image = self.images[0]
        elif msg["msg"] == "turn2death":
            self.terminated = True                        
    
    def update(self,dt):        
        self.nextimg -= dt
        if self.nextimg <= 0.0:            
            if self.state == "norm": 
                self.state = "gest"
                self.nextimg = random.random()*self.at
                self.actor.image = self.images[1]
            else:
                self.state = "norm"
                self.nextimg = random.randint(self.rt[0],self.rt[1])
                self.actor.image = self.images[0]
        
# --------------------------------------------------------
# --------------------------------------------------------
class BhAlternateDeath:
    def __init__(self,actor,img0,img1,t0=1,t1=1,alt=0):
        self.actor = actor
        self.images = [ GAME.loadImage(img0), GAME.loadImage(img1) ]
        self.t0,self.t1 = t0,t1
        self.changeState( "good" if alt==0 else "evil" )        
        
    def changeState(self,st):
        self.state = st
        self.at = self.t0 if st == "good" else self.t1
        self.actor.image = self.images[ 0 if st=="good" else 1 ]
        self.actor.collidable = st == "evil"
            
    def update(self,dt):
        self.at -= dt
        if self.at <= 0.0:
            self.changeState("evil" if self.state == "good" else "good")
        
# --------------------------------------------------------
# Transform player in the avatar. Collision and key responses code
# --------------------------------------------------------
class BhPlayer:
    def __init__(self,actor):
        self.actor = actor
        self.images = [ GAME.loadImage(self.actor.imageName,flipx=True), GAME.loadImage(self.actor.imageName)]
        self.actor.rect.midbottom = (GAME.SCREENRECT.centerx, GAME.SCREENRECT.bottom)
        self.actor.x, self.actor.y = self.actor.rect.left, self.actor.rect.top
        self.vx,self.vy = 0.0,0.0
        self.gtime,self.blasting = 0.0, 0.0
    
    def message(self,msg):
        if msg["msg"] == "playerdie":
            self.terminated = True
            createAnim( self.actor.x+self.actor.rect.width/2, \
                        self.actor.y+self.actor.rect.height/2, "x", period=0.02 )
            GAME.playSound( "xp", 0.1 )
            self.actor.addBehavior( BhPlayerPause(self.actor,"Press Space",color=(255,0,255),msg="playerspawn") )
        elif msg["msg"] == "lastblock":
            GAME.playSound( "bell", 0.1 )
            self.terminated = True
            self.actor.addBehavior( BhPlayerPause(self.actor,"Stage Clear!",(0,255,0),"stageclear") )
            GAME.curlevel += 1
        elif msg["msg"] == "stageclear":
            self.terminated = True
            self.actor.addBehavior( BhPlayerPause(self.actor,"Press Space",color=(255,0,255),msg="playerspawn") )
        elif msg["msg"] == "blastplayer":
            v,d = msg["vec"],msg.get("pw",500.0)            
            c = msg.get("o",None)
            if c : self.actor.x,self.actor.y = c[0]-self.actor.rect.width/2,c[1]-self.actor.rect.height/2
            self.vx, self.vy = v[0]*d, v[1]*d
            self.blasting = msg.get("bt",0.1)
            self.gtime = 0.0
    
    def update(self,dt):
        self.actor.x += self.vx*dt
        self.actor.y += self.vy*dt        
        xbounds = ( 0, GAME.SCREENRECT.right - self.actor.rect.width )
        ybounds = ( 0, GAME.SCREENRECT.bottom - self.actor.rect.height*2 )
        collblock = GAME.collision( (self.actor.x+self.actor.rect.width/2, self.actor.y+self.actor.rect.height/2), \
                                    Rect( (self.actor.x,self.actor.y), self.actor.rect.size ) )        
        if collblock:
            collblock.sendMessage( {"msg":"collision","player":self.actor, "vec":(self.vx,self.vy)} )
            GAME.sendMessage({"msg":"updatebounces","bounces":1})
            if collblock.response:
                self.blasting = 0.0
                xt, yt = self.actor.x, self.actor.y
                if math.fabs( self.actor.rect.centerx - collblock.rect.centerx ) <= \
                   math.fabs( self.actor.rect.centery - collblock.rect.centery ):
                    xt += self.actor.rect.width/2
                    if self.actor.rect.top > collblock.rect.top:
                        ybounds = ( collblock.rect.bottom, ybounds[1] )
                    else:
                        ybounds = ( 0, collblock.rect.top-self.actor.rect.height )
                        yt += self.actor.rect.height
                else:
                    yt += self.actor.rect.height/2
                    if self.actor.rect.right < collblock.rect.right:
                        xt += self.actor.rect.width
                        xbounds = ( 0, collblock.rect.left-self.actor.rect.width )
                    else:
                        xbounds = ( collblock.rect.right, xbounds[1] )
                createAnim( xt, yt, "t" )
                GAME.playSound( "click", 0.1 )
        self.actor.x = clamp(self.actor.x, xbounds[0], xbounds[1])
        self.actor.y = clamp(self.actor.y, ybounds[0], ybounds[1])
        
        if self.actor.x == xbounds[0] or self.actor.x == xbounds[1]: 
            self.vx *= -1.0
        else:
            self.vx += (0-self.vx)*dt*2.0
            
        self.gtime += dt
        self.blasting -= dt        
        if self.actor.y == ybounds[0] or self.actor.y == ybounds[1]: 
            if self.actor.y == ybounds[1] and ybounds[1] == (GAME.SCREENRECT.bottom - self.actor.rect.height*2):
                GAME.sendMessage( {"msg":"playerdie"} )
            self.vy *= -1.0
            if self.vy < 0.0:
                self.gtime = 0.0
                self.vy *= 0.5
            else:
                self.gtime = 0.2
        else:
            self.vy += (0-self.vy)*dt*3.0
        self.vy += 4.9*self.gtime*self.gtime*200.0*dt
        
        if self.blasting <= 0.0:
            if GAME.KEYPRESSED[K_LEFT]: 
                self.vx -= 600*dt                
                self.actor.image = self.images[0]
            elif GAME.KEYPRESSED[K_RIGHT] : 
                self.vx += 600*dt        
                self.actor.image = self.images[1]
            if GAME.KEYPRESSED[K_UP]      : 
                self.vy -= 1000*dt
                self.gtime = 0.0
            elif GAME.KEYPRESSED[K_DOWN]  : 
                self.vy += 3000*dt
            
        self.vx = clamp(self.vx, -1200, 1200)    


# --------------------------------------------------------
# Acts like a level
# --------------------------------------------------------
class BhLevel:
    def __init__(self,actor):
        self.actor = actor        
        self.deffont = GAME.loadFont("type_writer.ttf", 10)
        self.fontbig = GAME.loadFont("type_writer.ttf", 12)
        self.loadLevel()        
        self.updatePoints(0)
        self.updateBounces(0)
        self.updateRemains( )        
        
    def loadLevel(self):
        filedef = {}
        execfile( GAME.nextLevel(), filedef )
        mapdesc,mapdefs,mapinfo = filedef["MAP"], filedef["MAPDEFS"], filedef["INFO"]
        self.updateLevelInfo( str(GAME.curlevel%len(GAME.levels))+":"+mapinfo["name"] )
        self.remainBlocks = 0
        self.blocks = []
        for x in range(-1,21):
            self.blocks.append( createBlock( "t", pos=(x*32,14*32)) )
        for y in range(0,15):
            for x in range(0,20):
                b = mapdesc[y][x]
                if b in ["w","l","b","y","r","m","t","k","p"]:
                    self.blocks.append( createBlock(b,pos=(x*32,y*32)) )
                elif b == "s":
                    GAME.spawnpoint = (x*32,y*32)
                elif mapdefs.has_key(b):
                    defs = mapdefs[b]
                    b = defs[0]
                    self.blocks.append( createBlock( b, pos=(x*32,y*32), bhs=defs[1] ) )
                if b == "w" : self.remainBlocks += 1
        GAME.sendMessage( {"msg":"playerspawn"} )
                    
    def updateLevelInfo(self,name):
        self.lvlNameSprite = self.fontbig.render(name, 1, (255, 255, 255))
        self.lvlNamePos = self.lvlNameSprite.get_rect()
        self.lvlNamePos.topleft = (10,10)
        
    def updatePoints(self,p):        
        self.pointsSprite = self.deffont.render("P: " + str(p), 1, (255, 255, 0))
        self.pointsPos = self.pointsSprite.get_rect()
        self.pointsPos.topright = (GAME.SCREENRECT.right-10,10)
        
    def updateRemains(self):
        self.remSprite = self.deffont.render("R: " + str(self.remainBlocks), 1, (255, 255, 0))        
        self.remPos = self.remSprite.get_rect()
        self.remPos.topright = (GAME.SCREENRECT.right-10,21)
        
    def updateBounces(self,b):
        self.bouncesSprite = self.deffont.render("B: " + str(b), 1, (255,255,0))
        self.bouncesPos = self.bouncesSprite.get_rect()
        self.bouncesPos.topright = (GAME.SCREENRECT.right-10,32)
        
    def update(self,dt):
        GAME.draw( (10,self.lvlNameSprite, self.lvlNamePos) )
        GAME.draw( (10,self.pointsSprite, self.pointsPos) )
        GAME.draw( (10,self.remSprite, self.remPos) )
        GAME.draw( (10,self.bouncesSprite, self.bouncesPos) )
        
    def message(self,msg):
        if msg["msg"] == "updplayerstats":
            pl = msg["player"]
            self.updatePoints( pl.points )
            self.updateBounces( pl.bounces )
        elif msg["msg"] == "updateremains":
            self.remainBlocks += msg["remains"]
            if self.remainBlocks == 0:
                GAME.sendMessage( {"msg":"lastblock"} )              
            self.updateRemains()
        elif msg["msg"] == "stageclear":
            for a in self.blocks: 
                a.terminated = True
            self.loadLevel()

# --------------------------------------------------------
# Shows a message awaiting for space ("press space" and "stage clear" messages)
# --------------------------------------------------------
class BhPlayerPause:
    def __init__(self,actor,txt,color=(255,0,0),msg=""):
        self.actor = actor
        self.font = GAME.loadFont("type_writer.ttf", 24)
        self.pauseSprite = self.font.render(txt, 1, color,(0,0,0))
        self.pausePos = self.pauseSprite.get_rect()
        self.pausePos.center = GAME.SCREENRECT.center
        self.actor.visible = False
        self.msg = msg
        
    def update(self,dt):
        GAME.draw( (10,self.pauseSprite,self.pausePos) )
        if GAME.KEYPRESSED[K_SPACE]:
            self.terminated = True
            self.actor.addBehavior( BhPlayer(self.actor) )
            self.actor.visible = True
            GAME.sendMessage( {"msg":self.msg} )
   
# --------------------------------------------------------
# Represents the statistics for player
# --------------------------------------------------------
class BhPlayerStatus:
    def __init__(self,actor):
        self.actor = actor
        self.actor.points = 0
        self.actor.bounces = 0
        self.nextbounce = 0.0
        
    def message(self,msg):
        updatestats = False
        if msg["msg"] == "playerdie":
            self.actor.points -= 5
            if self.actor.points < 0: 
                self.actor.points = 0
            createTextAnim( -5, self.actor.x+self.actor.rect.width/2,\
                                  self.actor.y+self.actor.rect.height/2 )
            updatestats = True            
        elif msg["msg"] == "updatepoints":
            self.actor.points += msg["points"]
            createTextAnim( msg["points"], self.actor.x+self.actor.rect.width/2,\
                                             self.actor.y+self.actor.rect.height/2 )
            updatestats = True
        elif msg["msg"] == "updatebounces" and self.nextbounce < 0.0:
            self.nextbounce = 0.2
            self.actor.bounces += msg["bounces"]
            updatestats = True
        elif msg["msg"] == "playerspawn":
            self.actor.x, self.actor.y = GAME.spawnpoint
            self.actor.x += self.actor.rect.width/2
            self.actor.y += self.actor.rect.height/2
        if updatestats:
            GAME.sendMessage( { "msg":"updplayerstats", "player":self.actor} )
            
    def update(self,dt):
        self.nextbounce -= dt
        
# --------------------------------------------------------
# Creates an animation
# --------------------------------------------------------
def createAnim( x, y, anim, n=6, period=0.01 ):
    actor = Actor()    
    actor.addBehavior( BhDrawing(actor,"t0",pos=(x,y),zord=9) )
    actor.addBehavior( BhAnim(actor,anim,n,period) )
    GAME.addActor( actor )

# --------------------------------------------------------
# Creates a points animation
# --------------------------------------------------------
def createTextAnim( points, x, y, dur=0.8,col=(255,255,255) ):
    actor = Actor()
    actor.addBehavior( BhDrawing(actor,None,zord=9) )
    actor.addBehavior( BhTextAnim(actor, points, (x,y),dur,col) )
    GAME.addActor( actor )    

# --------------------------------------------------------
# Creates a block
# --------------------------------------------------------
def createBlock( bd, pos, bhs=[] ):
    actor = Actor()
    actor.addBehavior( BhDrawing(actor,bd+"block",pos) )
    if bd != "t": 
        actor.addBehavior( BhColliding(actor) )
    else:
        actor.addBehavior( BhMoverBlock(actor,1,8,1,0) )
        actor.zord = 0    
    if bd == "b":
        actor.addBehavior( BhBrokenBlock(actor) )
    elif bd == "y":
        actor.addBehavior( BhGestureBlock(actor,"yblock", "yblock2") )
        actor.addBehavior( BhYellowBlock(actor,False) )
    elif bd == "p":
        actor.addBehavior( BhSleepingBlock(actor) )
    elif bd == "w":
        actor.addBehavior( BhGestureBlock(actor,"wblock", "wblock2") )
        actor.addBehavior( BhWhiteBlock(actor) )    
    elif bd == "r":
        actor.addBehavior( BhShaking(actor) )
        actor.addBehavior( BhDeathBlock(actor,False) )
    elif bd == "k":        
        actor.addBehavior( BhDeathBlock(actor,False) )
        
    if bhs:
        for b in bhs:
            actor.addBehavior( eval(b) )
    GAME.addActor( actor )
    return actor

# --------------------------------------------------------
# Creates the player
# --------------------------------------------------------
def createPlayer(img):
    actor = Actor()
    actor.addBehavior( BhDrawing(actor,img,zord=9) )
    actor.addBehavior( BhPlayerPause(actor,"Press Space",color=(255,0,255),msg="playerspawn") )
    actor.addBehavior( BhPlayerStatus(actor) )    
    GAME.addActor( actor )

# --------------------------------------------------------
# Creates the level
# --------------------------------------------------------
def createLevel():
    actor = Actor()
    actor.addBehavior( BhLevel(actor) )
    GAME.addActor( actor )
        
# --------------------------------------------------------
# Entry point
# --------------------------------------------------------
def main():
    global GAME
    # Initialize
    pygame.init()
    GAME = GameClass( "block'em! game by Gyakoo", (640,480) )
    #pygame.mouse.set_visible(0)

    # Game Objects    
    createLevel()
    createPlayer("blocky")
       
    # Main Loop
    nextkey = 0.0
    finished = False
    while not finished:
        # -- CLOCK
        GAME.clock.tick(60)
        dt = GAME.clock.get_time()/1000.0
        
        # -- INPUT
        for event in pygame.event.get():
            if event.type == QUIT:
                finished = True
                break
        GAME.KEYPRESSED = pygame.key.get_pressed()
        finished = finished or GAME.KEYPRESSED[K_ESCAPE]
        if (GAME.KEYPRESSED[K_F5] or GAME.KEYPRESSED[K_F4]) and nextkey <= 0.0:
            GAME.curlevel += 1 if GAME.KEYPRESSED[K_F5] else -1
            GAME.sendMessage({"msg":"stageclear"})
            nextkey = .5
        nextkey -= dt
        
        # -- UPDATE
        GAME.update(dt)

    GAME.destroy()
    pygame.quit()

# Game when this script is executed, not imported
if __name__ == '__main__':
    try:
        main()
    except Exception,e:
        GAME.destroy()
        pygame.quit()
        raise e