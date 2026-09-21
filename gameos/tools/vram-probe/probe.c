// Wall 4 probe: can host-imported memory back a RENDERABLE image on NVIDIA/Linux?
// Build: gcc -O2 probe.c -lvulkan -o probe     Run: dgpu-exec-v2 ./probe
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

#define VK(x) do{ VkResult r=(x); if(r){ printf("  !! %s -> %d\n",#x,r); } }while(0)
#define MUST(x) do{ VkResult r=(x); if(r){ printf("FATAL %s -> %d\n",#x,r); exit(1);} }while(0)

static void flags_str(VkMemoryPropertyFlags f, char*out){
  out[0]=0;
  if(f&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)  strcat(out,"DEVICE_LOCAL ");
  if(f&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)  strcat(out,"HOST_VISIBLE ");
  if(f&VK_MEMORY_PROPERTY_HOST_COHERENT_BIT) strcat(out,"HOST_COHERENT ");
  if(f&VK_MEMORY_PROPERTY_HOST_CACHED_BIT)   strcat(out,"HOST_CACHED ");
  if(f&VK_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT) strcat(out,"LAZY ");
  if(!out[0]) strcat(out,"(none)");
}

int main(void){
  VkApplicationInfo ai={VK_STRUCTURE_TYPE_APPLICATION_INFO};
  ai.apiVersion=VK_API_VERSION_1_1;
  VkInstanceCreateInfo ici={VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ici.pApplicationInfo=&ai;
  VkInstance inst; MUST(vkCreateInstance(&ici,0,&inst));

  uint32_t n=0; MUST(vkEnumeratePhysicalDevices(inst,&n,0));
  VkPhysicalDevice*pds=malloc(n*sizeof(*pds)); vkEnumeratePhysicalDevices(inst,&n,pds);
  VkPhysicalDevice pd=VK_NULL_HANDLE; VkPhysicalDeviceProperties props;
  for(uint32_t i=0;i<n;i++){ VkPhysicalDeviceProperties p; vkGetPhysicalDeviceProperties(pds[i],&p);
    printf("device %u: %s\n",i,p.deviceName);
    if(strstr(p.deviceName,"NVIDIA")||strstr(p.deviceName,"RTX")){ pd=pds[i]; props=p; } }
  if(!pd){ printf("\n!! No NVIDIA device visible. Run through dgpu-exec-v2.\n"); return 1; }
  printf("\n=== USING: %s ===\n\n",props.deviceName);

  // ---- 1. what memory does this card actually expose? ----
  VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd,&mp);
  printf("--- HEAPS (%u) ---\n",mp.memoryHeapCount);
  for(uint32_t i=0;i<mp.memoryHeapCount;i++)
    printf("  heap %u: %7.0f MB  %s\n", i, mp.memoryHeaps[i].size/1048576.0,
      (mp.memoryHeaps[i].flags&VK_MEMORY_HEAP_DEVICE_LOCAL_BIT)?"DEVICE_LOCAL":"(host)");
  printf("--- MEMORY TYPES (%u) ---\n",mp.memoryTypeCount);
  char b[256];
  for(uint32_t i=0;i<mp.memoryTypeCount;i++){
    flags_str(mp.memoryTypes[i].propertyFlags,b);
    printf("  type %2u: heap %u  %s\n", i, mp.memoryTypes[i].heapIndex, b); }

  // ---- 2. is VK_EXT_external_memory_host present? ----
  uint32_t ec=0; vkEnumerateDeviceExtensionProperties(pd,0,&ec,0);
  VkExtensionProperties*ex=malloc(ec*sizeof(*ex));
  vkEnumerateDeviceExtensionProperties(pd,0,&ec,ex);
  int has_host=0,has_dmabuf=0,has_fd=0;
  for(uint32_t i=0;i<ec;i++){
    if(!strcmp(ex[i].extensionName,VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME)) has_host=1;
    if(!strcmp(ex[i].extensionName,"VK_EXT_external_memory_dma_buf")) has_dmabuf=1;
    if(!strcmp(ex[i].extensionName,"VK_KHR_external_memory_fd")) has_fd=1; }
  printf("\n--- EXTENSIONS ---\n");
  printf("  VK_EXT_external_memory_host   : %s\n", has_host?"YES":"NO");
  printf("  VK_EXT_external_memory_dma_buf: %s\n", has_dmabuf?"YES":"NO");
  printf("  VK_KHR_external_memory_fd     : %s\n", has_fd?"YES":"NO");
  if(!has_host){ printf("\n!! no external_memory_host - probe cannot continue\n"); return 1; }

  VkPhysicalDeviceExternalMemoryHostPropertiesEXT hp={
    VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT};
  VkPhysicalDeviceProperties2 p2={VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2}; p2.pNext=&hp;
  vkGetPhysicalDeviceProperties2(pd,&p2);
  printf("  minImportedHostPointerAlignment: %llu bytes\n",
         (unsigned long long)hp.minImportedHostPointerAlignment);

  // ---- 3. create device ----
  uint32_t qn=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,0);
  VkQueueFamilyProperties*qf=malloc(qn*sizeof(*qf));
  vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,qf);
  uint32_t qi=0; for(uint32_t i=0;i<qn;i++) if(qf[i].queueFlags&VK_QUEUE_GRAPHICS_BIT){qi=i;break;}
  float prio=1.f;
  VkDeviceQueueCreateInfo qci={VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
  qci.queueFamilyIndex=qi; qci.queueCount=1; qci.pQueuePriorities=&prio;
  const char*devext[]={VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME};
  VkDeviceCreateInfo dci={VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
  dci.queueCreateInfoCount=1; dci.pQueueCreateInfos=&qci;
  dci.enabledExtensionCount=1; dci.ppEnabledExtensionNames=devext;
  VkDevice dev; MUST(vkCreateDevice(pd,&dci,0,&dev));

  PFN_vkGetMemoryHostPointerPropertiesEXT getHostProps =
    (PFN_vkGetMemoryHostPointerPropertiesEXT)vkGetDeviceProcAddr(dev,"vkGetMemoryHostPointerPropertiesEXT");
  if(!getHostProps){ printf("!! vkGetMemoryHostPointerPropertiesEXT missing\n"); return 1; }

  // ---- 4. what memory types can a HOST POINTER be imported as? ----
  size_t align=hp.minImportedHostPointerAlignment, sz=align*1024; // ~4MB typical
  void*host=aligned_alloc(align,sz); memset(host,0,sz);
  VkMemoryHostPointerPropertiesEXT hpp={VK_STRUCTURE_TYPE_MEMORY_HOST_POINTER_PROPERTIES_EXT};
  VkResult hr=getHostProps(dev,VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT,host,&hpp);
  printf("\n--- HOST POINTER IMPORT ---\n");
  printf("  vkGetMemoryHostPointerProperties -> %d\n",hr);
  printf("  importable as memoryTypeBits = 0x%08x -> types:", hpp.memoryTypeBits);
  for(uint32_t i=0;i<mp.memoryTypeCount;i++) if(hpp.memoryTypeBits&(1u<<i)) printf(" %u",i);
  printf("\n");
  int host_devlocal=0;
  for(uint32_t i=0;i<mp.memoryTypeCount;i++)
    if((hpp.memoryTypeBits&(1u<<i)) &&
       (mp.memoryTypes[i].propertyFlags&VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) host_devlocal=1;
  printf("  any of them DEVICE_LOCAL? %s\n", host_devlocal?"YES":"NO");

  // ---- 5. THE QUESTION: can a renderable image use those types? ----
  struct { const char*name; VkImageTiling tiling; VkImageUsageFlags usage; } cases[] = {
    {"COLOR_ATTACHMENT|SAMPLED, OPTIMAL tiling", VK_IMAGE_TILING_OPTIMAL,
       VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT},
    {"COLOR_ATTACHMENT|SAMPLED, LINEAR tiling",  VK_IMAGE_TILING_LINEAR,
       VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT},
    {"SAMPLED only, OPTIMAL tiling",             VK_IMAGE_TILING_OPTIMAL,
       VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT},
  };
  printf("\n--- CAN A RENDERABLE IMAGE BIND HOST MEMORY? ---\n");
  for(unsigned c=0;c<sizeof(cases)/sizeof(cases[0]);c++){
    VkImageCreateInfo ic={VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    ic.imageType=VK_IMAGE_TYPE_2D; ic.format=VK_FORMAT_R8G8B8A8_UNORM;
    ic.extent=(VkExtent3D){512,512,1}; ic.mipLevels=1; ic.arrayLayers=1;
    ic.samples=VK_SAMPLE_COUNT_1_BIT; ic.tiling=cases[c].tiling; ic.usage=cases[c].usage;
    ic.sharingMode=VK_SHARING_MODE_EXCLUSIVE; ic.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED;
    VkImage img; VkResult ir=vkCreateImage(dev,&ic,0,&img);
    printf("  [%s]\n", cases[c].name);
    if(ir){ printf("     vkCreateImage failed (%d) - unsupported config\n",ir); continue; }
    VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev,img,&mr);
    printf("     image allows memoryTypeBits = 0x%08x\n", mr.memoryTypeBits);
    uint32_t inter = mr.memoryTypeBits & hpp.memoryTypeBits;
    printf("     INTERSECTION with host-importable = 0x%08x  -> %s\n",
           inter, inter? "NON-EMPTY (can try bind)":"EMPTY - host memory CANNOT back this image");
    if(inter){
      uint32_t t=0; while(!(inter&(1u<<t))) t++;
      VkImportMemoryHostPointerInfoEXT imp={
        VK_STRUCTURE_TYPE_IMPORT_MEMORY_HOST_POINTER_INFO_EXT};
      imp.handleType=VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT;
      imp.pHostPointer=host;
      VkMemoryAllocateInfo mai={VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
      mai.pNext=&imp; mai.allocationSize=(mr.size+align-1)/align*align; mai.memoryTypeIndex=t;
      VkDeviceMemory mem;
      VkResult ar=vkAllocateMemory(dev,&mai,0,&mem);
      printf("     import+alloc (type %u, %.1f MB) -> %d %s\n",
             t, mai.allocationSize/1048576.0, ar, ar?"FAILED":"OK");
      if(!ar){
        VkResult br=vkBindImageMemory(dev,img,mem,0);
        printf("     vkBindImageMemory -> %d  %s\n", br,
               br?"FAILED":"*** SUCCESS: renderable image bound to SYSTEM RAM ***");
        vkFreeMemory(dev,mem,0);
      }
    }
    vkDestroyImage(dev,img,0);
  }

  // ---- 6. control: plain buffer ----
  VkBufferCreateInfo bci={VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
  bci.size=1<<20; bci.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT;
  VkBuffer buf; if(!vkCreateBuffer(dev,&bci,0,&buf)){
    VkMemoryRequirements mr; vkGetBufferMemoryRequirements(dev,buf,&mr);
    printf("\n--- CONTROL: plain buffer ---\n");
    printf("  buffer allows 0x%08x, intersection 0x%08x -> %s\n",
      mr.memoryTypeBits, mr.memoryTypeBits&hpp.memoryTypeBits,
      (mr.memoryTypeBits&hpp.memoryTypeBits)?"host memory CAN back a buffer":"cannot");
    vkDestroyBuffer(dev,buf,0);
  }
  printf("\n");
  return 0;
}
