#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "hardware/dma.h"
#include "hardware/clocks.h"
#include "hardware/irq.h"
#define CLK 2
#define DAT 3
#define RATE 40000000u
#define N 1024
static uint32_t buf[2][N];
static uint ch[2];
static volatile uint8_t ready;
static volatile uint32_t losses;
static uint8_t bits[512];
static unsigned nb;
static bool prev,have,active,overflow;
static uint32_t quiet;
static uint8_t seen;
static uint32_t packets,parity_fail;
static const uint16_t instr[]={0x4002}; /* IN PINS,2 */
static const struct pio_program prog={instr,1,-1};
static void dma_irq(void){
 for(unsigned i=0;i<2;i++) if(dma_hw->ints0&(1u<<ch[i])){
  dma_hw->ints0=1u<<ch[i];
  if(ready&(1u<<i)) losses++;
  ready|=1u<<i;
  dma_channel_set_write_addr(ch[i],buf[i],false);
 }
}
static unsigned field(unsigned at,unsigned n){unsigned v=0;for(unsigned j=0;j<n;j++)v=(v<<1)|bits[at+j];return v;}
static bool parity(unsigned at,unsigned n){unsigned v=0;for(unsigned j=0;j<n;j++)v+=bits[at+j];return (v&1u)!=0;}
static bool byte(unsigned *at,uint8_t *v){if(*at+9>nb||!parity(*at,9))return false;*v=field(*at,8);*at+=9;return true;}
static void frame(void){
 if(overflow){printf("[ERROR] FRAME_OVERFLOW\\r\\n");return;}
 if(nb<31)return;
 unsigned sid=field(0,4);
 if(sid!=0&&sid!=6&&sid!=9)return;
 if(!parity(0,13)){parity_fail++;return;}
 unsigned cmd=field(4,8);
 if(cmd<0x30||cmd>0x3f)return;
 unsigned at=13;uint8_t hi,lo;
 if(!byte(&at,&hi)||!byte(&at,&lo))return;
 bool read=(cmd&8)!=0;
 unsigned count=(cmd&7)+1;
 uint8_t data[8];
 if(!read)for(unsigned i=0;i<count;i++)if(!byte(&at,&data[i]))return;
 uint8_t mask=sid==0?1:sid==6?2:4;
 if(!(seen&mask)){seen|=mask;printf("[EVENT] SID %02X ACTIVITY DETECTED\\r\\n",sid);}
 printf("[SID %02X] %s | %s | CMD:0x%02X | ADDR:0x%04X",sid,sid==0?"BB":sid==6?"PMK":"PMU",read?"EXT_READL":"EXT_WRITEL",cmd,(hi<<8)|lo);
 if(read)printf(" | DATA:UNVERIFIED");
 else{printf(" | DATA:");for(unsigned i=0;i<count;i++)printf("%s%02X",i?" ":"",data[i]);}
 printf(" | CANDIDATE\\r\\n");packets++;
}
static void sample(unsigned v){
 bool clk=v&1,dat=v&2;
 if(!have){prev=clk;have=true;return;}
 uint32_t gap=quiet;
 if(clk!=prev)quiet=0;else if(quiet<UINT32_MAX)quiet++;
 if(active&&quiet>RATE/100000u){frame();active=false;nb=0;overflow=false;}
 if(!prev&&clk){
  bool start=gap>=14&&gap<=28; /* 350-700ns at 40MSa/s, candidate only */
  if(!active){if(!start){prev=clk;return;}active=true;nb=0;overflow=false;}
  else if(start&&nb>=13){frame();nb=0;overflow=false;}
  if(nb<sizeof(bits))bits[nb++]=dat?1:0;else overflow=true;
 }
 prev=clk;
}
int main(void){
 stdio_init_all();sleep_ms(1500);
 printf("\\r\\n=== RP2040 SPMI SNIFFER - EXPERIMENTAL ===\\r\\n");
 printf("GP2=SCLK GP3=SDATA FILTER=00/06/09 RATE=40MSa/s\\r\\n");
 printf("[WARNING] SSC, turnaround, read data and capture integrity NOT VERIFIED\\r\\n");
 gpio_init(CLK);gpio_set_dir(CLK,GPIO_IN);gpio_disable_pulls(CLK);
 gpio_init(DAT);gpio_set_dir(DAT,GPIO_IN);gpio_disable_pulls(DAT);
 PIO p=pio0;uint off=pio_add_program(p,&prog),sm=pio_claim_unused_sm(p,true);
 pio_sm_config c=pio_get_default_sm_config();
 sm_config_set_in_pins(&c,CLK);sm_config_set_in_shift(&c,true,true,32);
 sm_config_set_fifo_join(&c,PIO_FIFO_JOIN_RX);
 sm_config_set_clkdiv(&c,(float)clock_get_hz(clk_sys)/RATE);
 sm_config_set_wrap(&c,off,off);
 pio_gpio_init(p,CLK);pio_gpio_init(p,DAT);
 pio_sm_set_consecutive_pindirs(p,sm,CLK,2,false);
 pio_sm_init(p,sm,off,&c);
 for(unsigned i=0;i<2;i++)ch[i]=dma_claim_unused_channel(true);
 for(unsigned i=0;i<2;i++){
  dma_channel_config d=dma_channel_get_default_config(ch[i]);
  channel_config_set_transfer_data_size(&d,DMA_SIZE_32);
  channel_config_set_read_increment(&d,false);channel_config_set_write_increment(&d,true);
  channel_config_set_dreq(&d,pio_get_dreq(p,sm,false));
  channel_config_set_chain_to(&d,ch[1-i]);
  dma_channel_configure(ch[i],&d,buf[i],&p->rxf[sm],N,false);
  dma_channel_set_irq0_enabled(ch[i],true);
 }
 irq_set_exclusive_handler(DMA_IRQ_0,dma_irq);irq_set_enabled(DMA_IRQ_0,true);
 pio_sm_set_enabled(p,sm,true);dma_channel_start(ch[0]);
 while(1){
  for(unsigned i=0;i<2;i++)if(ready&(1u<<i)){
   uint32_t s=save_and_disable_interrupts();ready&=~(1u<<i);restore_interrupts(s);
   for(unsigned j=0;j<N;j++){uint32_t w=buf[i][j];for(unsigned k=0;k<16;k++)sample((w>>(2*k))&3);}
  }
  if(losses){printf("[ERROR] DMA_OVERRUN=%lu\\r\\n",(unsigned long)losses);losses=0;}
  tight_loop_contents();
 }
}
