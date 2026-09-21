// Wall 4b: can an OPTIMALLY-TILED renderable image live in memory type 0 (heap 1 = host),
// and can the GPU actually render into it correctly? And how much can we get?
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>
#define MUST(x) do{ VkResult r=(x); if(r){ printf("FATAL %s -> %d\n",#x,r); exit(1);} }while(0)

int main(void){
  VkApplicationInfo ai={VK_STRUCTURE_TYPE_APPLICATION_INFO}; ai.apiVersion=VK_API_VERSION_1_1;
  VkInstanceCreateInfo ici={VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&ai;
  VkInstance inst; MUST(vkCreateInstance(&ici,0,&inst));
  uint32_t n=0; vkEnumeratePhysicalDevices(inst,&n,0);
  VkPhysicalDevice*pds=malloc(n*sizeof(*pds)); vkEnumeratePhysicalDevices(inst,&n,pds);
  VkPhysicalDevice pd=VK_NULL_HANDLE;
  for(uint32_t i=0;i<n;i++){VkPhysicalDeviceProperties p;vkGetPhysicalDeviceProperties(pds[i],&p);
    if(strstr(p.deviceName,"NVIDIA")) pd=pds[i];}
  if(!pd){printf("no nvidia\n");return 1;}
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd,&mp);

  uint32_t qn=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,0);
  VkQueueFamilyProperties*qf=malloc(qn*sizeof(*qf));
  vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,qf);
  uint32_t qi=0; for(uint32_t i=0;i<qn;i++) if(qf[i].queueFlags&VK_QUEUE_GRAPHICS_BIT){qi=i;break;}
  float pr=1.f; VkDeviceQueueCreateInfo qci={VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
  qci.queueFamilyIndex=qi;qci.queueCount=1;qci.pQueuePriorities=&pr;
  VkDeviceCreateInfo dci={VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
  dci.queueCreateInfoCount=1;dci.pQueueCreateInfos=&qci;
  VkDevice dev; MUST(vkCreateDevice(pd,&dci,0,&dev));
  VkQueue q; vkGetDeviceQueue(dev,qi,0,&q);

  // --- TEST 1: bind an OPTIMAL color attachment to memory type 0 (heap 1 = host) ---
  printf("=== TEST 1: OPTIMAL-tiled COLOR_ATTACHMENT in memory type 0 (heap %u) ===\n",
         mp.memoryTypes[0].heapIndex);
  VkImageCreateInfo ic={VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
  ic.imageType=VK_IMAGE_TYPE_2D; ic.format=VK_FORMAT_R8G8B8A8_UNORM;
  ic.extent=(VkExtent3D){1024,1024,1}; ic.mipLevels=1; ic.arrayLayers=1;
  ic.samples=VK_SAMPLE_COUNT_1_BIT; ic.tiling=VK_IMAGE_TILING_OPTIMAL;
  ic.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
  ic.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
  VkImage img; MUST(vkCreateImage(dev,&ic,0,&img));
  VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev,img,&mr);
  printf("  image size %.2f MB, allows types 0x%x\n", mr.size/1048576.0, mr.memoryTypeBits);
  if(!(mr.memoryTypeBits&1)){ printf("  !! type 0 not allowed for this image\n"); return 1; }
  VkMemoryAllocateInfo mai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
  mai.allocationSize=mr.size; mai.memoryTypeIndex=0;
  VkDeviceMemory mem; VkResult ar=vkAllocateMemory(dev,&mai,0,&mem);
  printf("  vkAllocateMemory(type 0) -> %d %s\n",ar,ar?"FAILED":"OK");
  if(ar) return 1;
  VkResult br=vkBindImageMemory(dev,img,mem,0);
  printf("  vkBindImageMemory -> %d %s\n",br,br?"FAILED":"OK");
  if(br) return 1;

  // --- TEST 2: actually render into it and read the pixels back ---
  printf("\n=== TEST 2: GPU clears it to a known colour, read back and verify ===\n");
  VkCommandPoolCreateInfo cpi={VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; cpi.queueFamilyIndex=qi;
  VkCommandPool cp; MUST(vkCreateCommandPool(dev,&cpi,0,&cp));
  VkCommandBufferAllocateInfo cbi={VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
  cbi.commandPool=cp;cbi.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;cbi.commandBufferCount=1;
  VkCommandBuffer cb; MUST(vkAllocateCommandBuffers(dev,&cbi,&cb));
  // readback buffer in host-visible mem
  VkBufferCreateInfo bci={VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
  bci.size=1024*1024*4; bci.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT;
  VkBuffer rb; MUST(vkCreateBuffer(dev,&bci,0,&rb));
  VkMemoryRequirements rbr; vkGetBufferMemoryRequirements(dev,rb,&rbr);
  uint32_t ht=0; for(uint32_t i=0;i<mp.memoryTypeCount;i++)
    if((rbr.memoryTypeBits&(1u<<i))&&(mp.memoryTypes[i].propertyFlags&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)
       &&(mp.memoryTypes[i].propertyFlags&VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)){ht=i;break;}
  VkMemoryAllocateInfo rmai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
  rmai.allocationSize=rbr.size; rmai.memoryTypeIndex=ht;
  VkDeviceMemory rmem; MUST(vkAllocateMemory(dev,&rmai,0,&rmem));
  MUST(vkBindBufferMemory(dev,rb,rmem,0));

  VkCommandBufferBeginInfo bi={VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
  MUST(vkBeginCommandBuffer(cb,&bi));
  VkImageMemoryBarrier ib={VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
  ib.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED; ib.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
  ib.srcQueueFamilyIndex=ib.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED; ib.image=img;
  ib.subresourceRange=(VkImageSubresourceRange){VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
  ib.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT;
  vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,0,0,0,1,&ib);
  VkClearColorValue col={{0.25f,0.5f,0.75f,1.0f}};
  VkImageSubresourceRange rg={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
  vkCmdClearColorImage(cb,img,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,&col,1,&rg);
  ib.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL; ib.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
  ib.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT; ib.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;
  vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,0,0,0,1,&ib);
  VkBufferImageCopy rgn={0}; rgn.imageSubresource=(VkImageSubresourceLayers){VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};
  rgn.imageExtent=(VkExtent3D){1024,1024,1};
  vkCmdCopyImageToBuffer(cb,img,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,rb,1,&rgn);
  MUST(vkEndCommandBuffer(cb));
  VkSubmitInfo si={VK_STRUCTURE_TYPE_SUBMIT_INFO}; si.commandBufferCount=1; si.pCommandBuffers=&cb;
  MUST(vkQueueSubmit(q,1,&si,VK_NULL_HANDLE));
  MUST(vkQueueWaitIdle(q));
  void*ptr; MUST(vkMapMemory(dev,rmem,0,VK_WHOLE_SIZE,0,&ptr));
  unsigned char*px=ptr;
  printf("  pixel[0] = %u,%u,%u,%u   (expect ~64,128,191,255)\n",px[0],px[1],px[2],px[3]);
  int ok = (px[0]>60&&px[0]<70)&&(px[1]>124&&px[1]<132)&&(px[2]>186&&px[2]<196);
  printf("  %s\n", ok?"*** VERIFIED: GPU rendered correctly into SYSTEM RAM ***":"!! pixel mismatch");
  vkUnmapMemory(dev,rmem);

  // --- TEST 3: how much can we get from heap 1 via type 0? ---
  printf("\n=== TEST 3: how much type-0 memory can we allocate? (heap 1 = %.0f MB) ===\n",
         mp.memoryHeaps[mp.memoryTypes[0].heapIndex].size/1048576.0);
  VkDeviceMemory chunks[64]; int nc=0; double total=0; const double CH=256.0;
  for(;nc<64;nc++){
    VkMemoryAllocateInfo a={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
    a.allocationSize=(VkDeviceSize)(CH*1048576); a.memoryTypeIndex=0;
    if(vkAllocateMemory(dev,&a,0,&chunks[nc])!=VK_SUCCESS) break;
    total+=CH;
  }
  printf("  allocated %.0f MB in %d x %.0fMB chunks from type 0 before failure\n",total,nc,CH);
  for(int i=0;i<nc;i++) vkFreeMemory(dev,chunks[i],0);
  printf("\n");
  return 0;
}
