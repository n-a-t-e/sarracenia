#!/usr/bin/env python3
#
# This file is part of sarracenia.
# The sarracenia suite is Free and is proudly provided by the Government of Canada
# Copyright (C) Her Majesty The Queen in Right of Canada, Environment Canada, 2008-2015
#
# Questions or bugs report: dps-client@ec.gc.ca
# sarracenia repository: git://git.code.sf.net/p/metpx/git
# Documentation: http://metpx.sourceforge.net/#SarraDocumentation
#
# sr_pika.py : python3 utility tools from python's pika library
#
#
# Code contributed by:
#  Michel Grenier - Shared Services Canada
#  Last Revision  : Aug 11 12:41:54 UTC 2017
#
########################################################################
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, 
#  but WITHOUT ANY WARRANTY; without even the implied warranty of 
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
#

import pika, sys, time


# ==========
# amqplib message
# ==========

class Message:

   def __init__(self,logger):
       self.logger        = logger
       self.delivery_info = {}
       self.properties    = {}

   def pika_to_amqplib(self, method_frame, properties, body ):
       try :
               self.body  = body

               self.delivery_info['exchange']         = method_frame.exchange
               self.delivery_info['routing_key']      = method_frame.routing_key
               self.delivery_tag                      = method_frame.delivery_tag

               self.properties['application_headers'] = properties.headers
       except:
               (stype, value, tb) = sys.exc_info()
               self.logger.error("Type: %s, Value: %s" % (stype, value))
               self.logger.error("in pika to amqplib %s %s" %(vars(method_frame),vars(properties)))


# ==========
# HostConnect
# ==========

class HostConnect:

   def __init__(self, logger = None):

       self.asleep     = False
       self.loop       = True

       self.connection = None
       self.channel    = None
       self.ssl        = False

       self.logger     = logger

       self.protocol   = 'amqp'
       self.host       = 'localhost'
       self.port       = None
       self.user       = 'guest'
       self.passwd     = 'guest'

       self.rebuilds   = []
       self.toclose    = []

       self.sleeping   = None

   def add_build(self,func):
       self.rebuilds.append(func)

   def add_sleeping(self,func):
       self.sleeping = func
       
   def close(self):
       for channel in self.toclose:
           self.logger.debug("closing channel_id: %s" % channel.channel_number)
           try:    channel.close()
           except: pass
       try:    self.connection.close()
       except: pass
       self.toclose    = []
       self.connection = None

   def connect(self):

       if self.sleeping != None :
          self.asleep = self.sleeping()

       if self.asleep : return

       while True:
          try:
               # connect
               self.logger.debug("Connecting %s %s (ssl %s)" % (self.host,self.user,self.ssl) )
               host = self.host
               if self.port   != None : host = host + ':%s' % self.port
               self.logger.debug("%s://%s:<pw>@%s%s ssl=%s" % (self.protocol,self.user,host,self.vhost,self.ssl))
               credentials = pika.PlainCredentials(self.user, self.password)
               parameters  = pika.connection.ConnectionParameters(self.host,self.port,self.vhost,credentials,ssl=self.ssl)
               self.connection = pika.BlockingConnection(parameters)
               self.channel    = self.new_channel()
               self.logger.debug("Connected ")
               for func in self.rebuilds:
                   func()
               break
          except:
               (stype, svalue, tb) = sys.exc_info()
               self.logger.error("AMQP Sender cannot connect to: %s" % self.host)
               self.logger.error("Type=%s, Value=%s" % (stype, svalue))
               if not self.loop : sys.exit(1)
               self.logger.error("Sleeping 5 seconds ...")
               time.sleep(5)

   def exchange_declare(self,exchange,edelete=False,edurable=True):
       try    :
                    self.channel.exchange_declare(exchange, 'topic', auto_delete=edelete,durable=edurable)
                    self.logger.info("declaring exchange %s (%s@%s)" % (exchange,self.user,self.host))
       except :
                    (stype, svalue, tb) = sys.exc_info()
                    self.logger.error("could not declare exchange %s (%s@%s)" % (exchange,self.user,self.host))
                    self.logger.error("Type=%s, Value=%s" % (stype, svalue))

   def exchange_delete(self,exchange):
       try    :
                    self.channel.exchange_delete(exchange)
                    self.logger.info("deleting exchange %s (%s@%s)" % (exchange,self.user,self.host))
       except :
                    (stype, svalue, tb) = sys.exc_info()
                    self.logger.error("could not delete exchange %s (%s@%s)" % (exchange,self.user,self.host))
                    self.logger.error("Type=%s, Value=%s" % (stype, svalue))


   def new_channel(self):
       channel = self.connection.channel()
       self.toclose.append(channel)
       return channel

   def queue_delete(self,queue_name):
       self.logger.info("deleting queue %s (%s@%s)" % (queue_name,self.user,self.host))
       try    :
                    self.channel.queue_delete(queue_name)
       except :
                    self.logger.warning("could not delete queue %s (%s@%s)" % (queue_name,self.user,self.host))

   def reconnect(self):
       self.close()
       self.connect()

   def set_credentials(self,protocol,user,password,host,port,vhost):
       self.protocol = protocol
       self.user     = user
       self.password = password
       self.host     = host
       self.port     = port
       self.vhost    = vhost

       if self.protocol == 'amqps' : self.ssl = True
       if self.vhost    == None    : self.vhost = '/'
       if self.vhost    == ''      : self.vhost = '/'

   def set_url(self,url):
       self.protocol = url.scheme
       self.user     = url.username
       self.password = url.password
       self.host     = url.hostname
       self.port     = url.port
       self.vhost    = url.path

       if self.protocol == 'amqps' : 
          self.ssl = True
          if self.port == None :
               self.port=5671

       if self.vhost    == None    : self.vhost = '/'
       if self.vhost    == ''      : self.vhost = '/'


# ==========
# Consumer
# ==========

class Consumer:

   def __init__(self,hostconnect):

      self.hc       = hostconnect
      self.logger   = self.hc.logger
      self.prefetch = 20

      self.exchange_type = 'topic'

      self.hc.add_build(self.build)

      # truncated exponential backoff for consume...
      self.sleep_max  = 1
      self.sleep_min = 0.01
      self.sleep_now = self.sleep_min

      self.raw_msg   = Message(self.logger)

   def add_prefetch(self,prefetch):
       self.prefetch = prefetch

   def build(self):
       self.logger.debug("building consumer")
       self.channel = self.hc.new_channel()
       if self.prefetch != 0 :
          prefetch_size = 0      # dont care
          a_global      = False  # only apply here
          self.channel.basic_qos(prefetch_size,self.prefetch,a_global)
       
   def ack(self,msg):
       self.logger.debug("--------------> ACK")
       self.logger.debug("--------------> %s" % msg.delivery_tag )
       self.channel.basic_ack(msg.delivery_tag)

   def consume(self,queuename):

       msg = None

       if not self.hc.asleep :
              try :
                     method_frame, properties, body = self.channel.basic_get(queuename)
                     if method_frame and properties and body :
                        self.raw_msg.pika_to_amqplib(method_frame, properties, body )
                        msg = self.raw_msg

              except :
                     (stype, value, tb) = sys.exc_info()
                     self.logger.error("Type: %s, Value: %s" % (stype, value))
                     self.logger.error("Could not consume in queue %s" % queuename )
                     if self.hc.loop :
                        self.hc.reconnect()
                        self.logger.debug("consume resume ok")
                        if not self.hc.asleep : msg = self.consume(queuename)
       else:
              time.sleep(5)

       # when no message sleep for 1 sec. (value taken from old metpx)
       # *** value 0.01 was tested and would simply raise cpu usage of broker
       # to unacceptable level with very fews processes (~20) trying to consume messages
       # remember that instances and broker sharing messages add up to a lot of consumers

       if msg == None : 
          #self.logger.debug(" no messages received, sleep %5.2fs" % self.sleep_now)
          time.sleep(self.sleep_now)
          self.sleep_now = self.sleep_now * 2
          if self.sleep_now > self.sleep_max : 
                 self.sleep_now = self.sleep_max

       if msg != None :
          self.sleep_now = self.sleep_min 
          #self.logger.debug("--------------> GOT")

       return msg

# ==========
# Publisher
# ==========

class Publisher:

   def __init__(self,hostconnect):
       self.hc     = hostconnect
       self.logger = self.hc.logger
       self.hc.add_build(self.build)

   def build(self):
       self.channel = self.hc.new_channel()
       self.channel.confirm_delivery()
       
   def publish(self,exchange_name,exchange_key,message,mheaders):
       try :
              properties = pika.BasicProperties(content_type='text/plain', delivery_mode=1, headers=mheaders)
              self.channel.basic_publish(exchange_name, exchange_key, message, properties, True )
              return True
       except :
              if self.hc.loop :
                 (stype, value, tb) = sys.exc_info()
                 self.logger.error("Type: %s, Value: %s" % (stype, value))
                 self.logger.error("Sleeping 5 seconds ... and reconnecting")
                 time.sleep(5)
                 self.hc.reconnect()
                 if self.hc.asleep : return False
                 return self.publish(exchange_name,exchange_key,message,mheaders)
              else:
                 (etype, evalue, tb) = sys.exc_info()
                 self.logger.error("Type: %s, Value: %s" %  (etype, evalue))
                 self.logger.error("could not publish %s %s %s %s" % (exchange_name,exchange_key,message,mheaders))
                 return False


# ==========
# Queue
# ==========

class Queue:

   def __init__(self,hc,qname,auto_delete=False,durable=False,reset=False):

       self.hc          = hc
       self.logger      = self.hc.logger
       self.name        = qname
       self.qname       = qname
       self.auto_delete = False
       self.durable     = durable
       self.reset       = reset

       self.expire      = 0
       self.message_ttl = 0

       self.bindings    = []

       self.hc.add_build(self.build)

   def add_binding(self,exchange_name,exchange_key):
       self.bindings.append( (exchange_name,exchange_key) )

   def add_expire(self, expire):
       self.expire = expire

   def add_message_ttl(self, message_ttl):
       self.message_ttl = message_ttl

   def bind(self, exchange_name,exchange_key):
       self.channel.queue_bind(self.qname, exchange_name, exchange_key )

   def build(self):
       self.logger.debug("building queue %s" % self.name)
       self.channel = self.hc.new_channel()

       # queue arguments
       args = {}
       if self.expire > 0 :
          args   = {'x-expires' : self.expire }
       if self.message_ttl > 0 :
          args   = {'x-message-ttl' : self.message_ttl }

       # reset 
       if self.reset :
          try    : self.channel.queue_delete( self.name )
          except : self.logger.debug("could not delete queue %s (%s@%s)" % (self.name,self.hc.user,self.hc.host))
                  
       # create queue
       try:
               q_dclr_ok = self.channel.queue_declare( self.name,
                                   passive=False, durable=self.durable, exclusive=False,
                                   auto_delete=self.auto_delete,
                                   arguments= args )

               method = q_dclr_ok.method

               self.qname, msg_count, consumer_count = method.queue, method.message_count, method.consumer_count
       
       except : 
              self.logger.error( "queue declare: %s failed...(%s@%s) permission issue ?" % (self.name,self.hc.user,self.hc.host))
              (etype, evalue, tb) = sys.exc_info()
              self.logger.error("Type: %s, Value: %s" %  (etype, evalue))

       # queue bindings
       for exchange_name,exchange_key in self.bindings:
           self.logger.debug("binding queue to exchange=%s with key=%s" % (exchange_name,exchange_key))
           try:
              self.bind(exchange_name, exchange_key )
           except : 
              self.logger.error( "bind queue: %s to exchange: %s with key: %s failed.." % \
                                 (self.name,exchange_name, exchange_key ) )
              self.logger.error( "Permission issue with %s@%s or exchange %s not found." % \
                                 (self.hc.user,self.hc.host,exchange_name ) )

       self.logger.debug("queue build done")