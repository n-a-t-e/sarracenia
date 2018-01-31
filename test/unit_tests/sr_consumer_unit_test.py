#!/usr/bin/env python3

try :    
         from sr_consumer       import *
except : 
         from sarra.sr_consumer import *


# ===================================
# self_test
# ===================================

class test_logger:
      def silence(self,str):
          pass
      def __init__(self):
          self.debug   = self.silence
          self.error   = print
          self.info    = self.silence
          self.warning = self.silence

def self_test():

    failed = False

    logger = test_logger()

    opt1   = 'accept .*bulletins.*'
    opt2   = 'reject .*'

    #setup consumer to catch first post
    cfg = sr_config()
    cfg.defaults()
    cfg.logger         = logger
    cfg.debug          = True
    cfg.broker         = urllib.parse.urlparse("amqp://anonymous:anonymous@dd.weather.gc.ca/")
    cfg.prefetch       = 10
    cfg.bindings       = [ ( 'xpublic', 'v02.post.#') ]
    cfg.durable        = False
    cfg.expire         = 60 * 1000 # 60 secs
    cfg.message_ttl    = 10 * 1000 # 10 secs
    cfg.user_cache_dir = os.getcwd()
    cfg.config_name    = "test"
    cfg.queue_name     = None
    cfg.retry_path     = '/tmp/retry'
    cfg.option( opt1.split()  )
    cfg.option( opt2.split()  )

    consumer = sr_consumer(cfg)

    # loop 100 times to try to catch a bulletin

    i = 0
    while True :
          ok, msg = consumer.consume()
          if ok: break

          i = i + 1
          if i == 100 : 
             msg = None
             break

    os.unlink(consumer.queuepath)

    consumer.cleanup()

    if msg == None :
       print("test 01: sr_consumer TEST Failed no message")
       failed = True

    elif not 'bulletins' in msg.notice :
       print("test 02: sr_consumer TEST Failed not a bulletin")
       failed = True


    if not failed :
                    print("sr_consumer.py TEST PASSED")
    else :          
                    print("sr_consumer.py TEST FAILED")
                    sys.exit(1)


# ===================================
# MAIN
# ===================================

def main():

    try:    self_test()
    except: 
            (stype, svalue, tb) = sys.exc_info()
            print("%s, Value: %s" % (stype, svalue))
            print("sr_consumer.py TEST FAILED")
            sys.exit(1)

    sys.exit(0)

# =========================================
# direct invocation : self testing
# =========================================

if __name__=="__main__":
   main()