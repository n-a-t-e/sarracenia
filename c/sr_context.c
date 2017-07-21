/* vim:set ft=c ts=2 sw=2 sts=2 et cindent: */

/*
 * Usage info after license block.
 *
 * This code is by Peter Silva copyright (c) 2017 part of MetPX.
 * copyright is to the Government of Canada. code is GPL.
 *
 * based on a amqp_sendstring from rabbitmq-c package
 * the original license is below:
 */

/* 
  Minimal c implementation to allow posting of sr_post(7) messages.
  It has a lot of limitations, and no error checking for now.

  how to use:

  In a shell, to use an sr_config(7) style configuration file:
  set the SR_POST_CONFIG environment variable to the name of the
  file to use.

 
 limitations:
    - Doesn't support document_root, absolute paths posted.
    - Doesn't support cache.
    - does support csv for url, to allow load spreading.
    - seems to be about 30x faster than python version.

 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <time.h>
#include <fcntl.h>
#include <linux/limits.h>

#include <openssl/md5.h>
#include <openssl/sha.h>

#include <stdint.h>
#include <amqp_tcp_socket.h>
#include <amqp_ssl_socket.h>
#include <amqp.h>
#include <amqp_framing.h>

#include "sr_context.h"


void sr_amqp_error_print(int x, char const *context)
{
  if (x < 0) {
    fprintf(stderr, "%s: %s\n", context, amqp_error_string2(x));
    return;
  }
}

void sr_amqp_reply_print(amqp_rpc_reply_t x, char const *context)
{
  switch (x.reply_type) {
  case AMQP_RESPONSE_NORMAL:
    return;

  case AMQP_RESPONSE_NONE:
    fprintf(stderr, "%s: missing RPC reply type!\n", context);
    break;

  case AMQP_RESPONSE_LIBRARY_EXCEPTION:
    fprintf(stderr, "%s: %s\n", context, amqp_error_string2(x.library_error));
    break;
  
  case AMQP_RESPONSE_SERVER_EXCEPTION:
    switch (x.reply.id) {
    case AMQP_CONNECTION_CLOSE_METHOD: {
      amqp_connection_close_t *m = (amqp_connection_close_t *) x.reply.decoded;
      fprintf(stderr, "%s: server connection error %uh, message: %.*s\n",
              context,
              m->reply_code,
              (int) m->reply_text.len, (char *) m->reply_text.bytes);
      break;
    }
    case AMQP_CHANNEL_CLOSE_METHOD: {
      amqp_channel_close_t *m = (amqp_channel_close_t *) x.reply.decoded;
      fprintf(stderr, "%s: server channel error %uh, message: %.*s\n",
              context,
              m->reply_code,
              (int) m->reply_text.len, (char *) m->reply_text.bytes);
      break;
    }
    default:
      fprintf(stderr, "%s: unknown server error, method id 0x%08X\n", context, x.reply.id);
      break;
    }
    break;
  }
}



struct sr_context *sr_context_connect(struct sr_context *sr_c) {

 /* set up a connection given a context.
  */

  signed int status;
  amqp_rpc_reply_t reply;
  amqp_channel_open_ok_t *open_status;

  sr_c->conn = amqp_new_connection();

  if ( !strcmp(sr_c->scheme,"amqps") ) {
     sr_c->socket = amqp_ssl_socket_new(sr_c->conn);
     if (!(sr_c->socket)) {
        fprintf( stderr, "failed to create SSL amqp client socket.\n" );
        return(NULL);
     }

     amqp_ssl_socket_set_verify_peer(sr_c->socket, 0);
     amqp_ssl_socket_set_verify_hostname(sr_c->socket, 0);

  } else {
     sr_c->socket = amqp_tcp_socket_new(sr_c->conn);
     if (!(sr_c->socket)) {
        fprintf( stderr, "failed to create AMQP client socket. \n" );
        return(NULL);
     }
  }

  status = amqp_socket_open(sr_c->socket, sr_c->hostname, sr_c->port);
  if (status < 0) {
    sr_amqp_error_print(status, "failed opening AMQP socket");
    return(NULL);
  }

  reply = amqp_login(sr_c->conn, "/", 0, 131072, 0, AMQP_SASL_METHOD_PLAIN, sr_c->user, sr_c->password);
  if (reply.reply_type != AMQP_RESPONSE_NORMAL ) {
    sr_amqp_reply_print(reply, "failed AMQP login");
    return(NULL);
  }

  open_status = amqp_channel_open(sr_c->conn, 1);
  if (open_status == NULL ) {
    fprintf(stderr, "failed AMQP amqp_channel_open\n");
    return(NULL);
  }

  reply = amqp_get_rpc_reply(sr_c->conn);
  if (reply.reply_type != AMQP_RESPONSE_NORMAL ) {
    sr_amqp_reply_print(reply, "failed AMQP get_rpc_reply");
    return(NULL);
  }

  if ( (sr_c->cfg!=NULL) && sr_c->cfg->debug )
     fprintf( stderr, "sr_context_connect succeeded!\n" );

  return(sr_c);
}


struct sr_context *sr_context_init_config(struct sr_config_t *sr_cfg) 
{

  struct sr_context *sr_c;
  char *buf;
  int len;
  struct timespec ts;

  // seed for random checksums... random enough...
  clock_gettime( CLOCK_REALTIME , &ts);
  srandom(ts.tv_nsec);

  sr_c = (struct sr_context *)malloc(sizeof(struct sr_context));

  sr_c->cfg = sr_cfg;
  sr_c->conn = NULL;

  if (!(sr_cfg->broker_specified)) 
  {
    fprintf( stderr, "no broker given\n" );
    return( NULL );
  }

  sr_c->scheme = sr_cfg->broker.scheme.first ;
  sr_c->hostname = sr_cfg->broker.hostText.first ;
  
  if ( sr_cfg->broker.portText.first == NULL ) {
     if ( !strcmp(sr_c->scheme,"amqps") ) sr_c->port = 5671;
     else sr_c->port= 5672;
  } else sr_c->port = atol( sr_cfg->broker.portText.first );
  

  if (sr_cfg->exchange==NULL) 
  {
    fprintf( stderr, "no exchange given\n" );
    return( NULL );
  }

  sr_c->exchange = sr_cfg->exchange ;
  
  len = strcspn(sr_cfg->broker.userInfo.first, ":");

  buf = (char *)malloc(len+1);

  strncpy(buf, sr_cfg->broker.userInfo.first, len );

  sr_c->user = buf;
  sr_c->password = sr_cfg->broker.userInfo.first + len +1 ;
  sr_c->url = sr_cfg->url;

  sr_c->to = ( sr_cfg->to == NULL ) ? sr_cfg->broker.hostText.first : sr_cfg->to;
  sr_c->socket = NULL;

  if ( (sr_c->cfg!=NULL) && sr_c->cfg->debug )
  {
     fprintf( stderr, "debug broker: %s://%s:%s@%s:%d\n", 
       sr_c->scheme, sr_c->user, (sr_c->password)?"<pw>":"<null>", sr_c->hostname, sr_c->port );
  }
  
  return( sr_c );

}

void sr_context_close(struct sr_context *sr_c) 
{

  amqp_rpc_reply_t reply;
  signed int status;

  reply = amqp_channel_close(sr_c->conn, 1, AMQP_REPLY_SUCCESS);
  if (reply.reply_type != AMQP_RESPONSE_NORMAL) {
      fprintf( stderr, "sr_cpost: amqp channel close failed.\n");
      return;
  }

  reply = amqp_connection_close(sr_c->conn, AMQP_REPLY_SUCCESS);
  if (reply.reply_type != AMQP_RESPONSE_NORMAL) {
      fprintf( stderr, "sr_cpost: amqp connection close failed.\n");
      return;
  }

  status = amqp_destroy_connection(sr_c->conn);
  if (status < 0 ) 
  {
      fprintf( stderr, "sr_cpost: amqp context close failed.\n");
      return;
  }
  free(sr_c->user);

}


