// Which real-game resource types can live in memory type 0 (system RAM)?
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>
#define MUST(x) do{VkResult r=(x); if(r){printf("FATAL %s->%d\n",#x,r);exit(1);} }while(0)
int main(void){
  VkApplicationInfo ai={VK_STRUCTURE_TYPE_APPLICATION_INFO}; ai.apiVersion=VK_API_VERSION_1_1;
  VkInstanceCreateInfo ici={VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&ai;
  VkInstance inst; MUST(vkCreateInstance(&ici,0,&inst));
  uint32_t n=0; vkEnumeratePhysicalDevices(inst,&n,0);
  VkPhysicalDevice*p=malloc(n*sizeof(*p)); vkEnumeratePhysicalDevices(inst,&n,p);
  VkPhysicalDevice pd=0; for(uint32_t i=0;i<n;i++){VkPhysicalDeviceProperties q;
    vkGetPhysicalDeviceProperties(p[i],&q); if(strstr(q.deviceName,"NVIDIA")) pd=p[i];}
  if(!pd){puts("no nvidia");return 1;}
  uint32_t qn=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,0);
  VkQueueFamilyProperties*qf=malloc(qn*sizeof(*qf));
  vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,qf);
  uint32_t qi=0; for(uint32_t i=0;i<qn;i++) if(qf[i].queueFlags&VK_QUEUE_GRAPHICS_BIT){qi=i;break;}
  float pr=1; VkDeviceQueueCreateInfo qc={VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
  qc.queueFamilyIndex=qi;qc.queueCount=1;qc.pQueuePriorities=&pr;
  VkDeviceCreateInfo dc={VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
  dc.queueCreateInfoCount=1;dc.pQueueCreateInfos=&qc;
  VkDevice dev; MUST(vkCreateDevice(pd,&dc,0,&dev));

  struct C{const char*n;VkFormat f;VkImageUsageFlags u;VkSampleCountFlagBits s;uint32_t w,h,mips,layers;} cases[]={
   {"colour RT 1080p RGBA8",        VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,VK_SAMPLE_COUNT_1_BIT,1920,1080,1,1},
   {"colour RT 1080p RGBA16F(HDR)", VK_FORMAT_R16G16B16A16_SFLOAT,VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,VK_SAMPLE_COUNT_1_BIT,1920,1080,1,1},
   {"colour RT 2880x1800 RGBA8",    VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,VK_SAMPLE_COUNT_1_BIT,2880,1800,1,1},
   {"depth D32_SFLOAT",             VK_FORMAT_D32_SFLOAT,     VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,VK_SAMPLE_COUNT_1_BIT,1920,1080,1,1},
   {"depth+stencil D24S8",          VK_FORMAT_D24_UNORM_S8_UINT,VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,VK_SAMPLE_COUNT_1_BIT,1920,1080,1,1},
   {"MSAA 2x colour",               VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,VK_SAMPLE_COUNT_2_BIT,1920,1080,1,1},
   {"MSAA 4x colour",               VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,VK_SAMPLE_COUNT_4_BIT,1920,1080,1,1},
   {"BC1 texture 2048 +mips",       VK_FORMAT_BC1_RGBA_UNORM_BLOCK,VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT,VK_SAMPLE_COUNT_1_BIT,2048,2048,11,1},
   {"BC3 texture 2048 +mips",       VK_FORMAT_BC3_UNORM_BLOCK,VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT,VK_SAMPLE_COUNT_1_BIT,2048,2048,11,1},
   {"BC7 texture 2048 +mips",       VK_FORMAT_BC7_UNORM_BLOCK,VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT,VK_SAMPLE_COUNT_1_BIT,2048,2048,11,1},
   {"storage image RGBA8",          VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_STORAGE_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,VK_SAMPLE_COUNT_1_BIT,1920,1080,1,1},
   {"storage image RGBA16F",        VK_FORMAT_R16G16B16A16_SFLOAT,VK_IMAGE_USAGE_STORAGE_BIT,VK_SAMPLE_COUNT_1_BIT,1920,1080,1,1},
   {"cubemap array 1024 x6 +mips",  VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT,VK_SAMPLE_COUNT_1_BIT,1024,1024,11,6},
   {"shadow map array D32 x4",      VK_FORMAT_D32_SFLOAT,     VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,VK_SAMPLE_COUNT_1_BIT,2048,2048,1,4},
  };
  printf("%-32s %10s  %-9s %s\n","resource","size MB","types","type 0 (SYSTEM RAM) usable?");
  printf("%.86s\n","--------------------------------------------------------------------------------------");
  int ok=0,tot=0;
  for(unsigned c=0;c<sizeof(cases)/sizeof(*cases);c++){
    VkImageCreateInfo ic={VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    ic.imageType=VK_IMAGE_TYPE_2D; ic.format=cases[c].f;
    ic.extent=(VkExtent3D){cases[c].w,cases[c].h,1};
    ic.mipLevels=cases[c].mips; ic.arrayLayers=cases[c].layers;
    ic.samples=cases[c].s; ic.tiling=VK_IMAGE_TILING_OPTIMAL; ic.usage=cases[c].u;
    ic.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
    if(cases[c].layers==6) ic.flags=VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT;
    VkImage im; VkResult r=vkCreateImage(dev,&ic,0,&im);
    if(r){ printf("%-32s %10s  %-9s %s\n",cases[c].n,"-","-","(image config unsupported)"); continue; }
    VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev,im,&mr);
    tot++;
    int t0 = !!(mr.memoryTypeBits & 1);
    // actually try it
    const char*verdict="NO";
    if(t0){
      VkMemoryAllocateInfo a={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
      a.allocationSize=mr.size; a.memoryTypeIndex=0;
      VkDeviceMemory m;
      if(vkAllocateMemory(dev,&a,0,&m)==VK_SUCCESS){
        verdict = vkBindImageMemory(dev,im,m,0)==VK_SUCCESS ? "YES (bound)" : "alloc ok, BIND FAILED";
        if(!strcmp(verdict,"YES (bound)")) ok++;
        vkFreeMemory(dev,m,0);
      } else verdict="type allowed but ALLOC FAILED";
    }
    printf("%-32s %10.1f  0x%-7x %s\n",cases[c].n,mr.size/1048576.0,mr.memoryTypeBits,verdict);
    vkDestroyImage(dev,im,0);
  }
  printf("%.86s\n","--------------------------------------------------------------------------------------");
  printf("  %d of %d resource classes can be placed in SYSTEM RAM\n",ok,tot);
  return 0;
}
