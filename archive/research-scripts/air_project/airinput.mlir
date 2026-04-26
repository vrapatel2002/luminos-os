#map = affine_map<(d0, d1, d2, d3) -> ()>
#map1 = affine_map<(d0, d1, d2, d3) -> (d1, d0, d2, d3)>
#map2 = affine_map<(d0, d1, d2, d3, d4, d5) -> (d2, d0, d3, d5)>
#map3 = affine_map<(d0, d1, d2, d3, d4, d5) -> (d1, d2, d5, d4)>
#map4 = affine_map<(d0, d1, d2, d3, d4, d5) -> (d1, d0, d3, d4)>
#map5 = affine_map<()[s0] -> (s0 + 1)>
module {
  func.func @int8_matmul_kernel(%arg0: memref<*xi8> {tt.divisibility = 16 : i32}, %arg1: memref<*xi8> {tt.divisibility = 16 : i32}, %arg2: memref<*xi32> {tt.divisibility = 16 : i32}, %arg3: i32, %arg4: i32, %arg5: i32, %arg6: i32, %arg7: i32, %arg8: i32) {
    %c1 = arith.constant 1 : index
    %c9 = arith.constant 9 : index
    air.launch (%arg9, %arg10, %arg11) in (%arg12=%c9, %arg13=%c1, %arg14=%c1) args(%arg15=%arg0, %arg16=%arg1, %arg17=%arg2) : memref<*xi8>, memref<*xi8>, memref<*xi32> {
      air.segment @int8_matmul_kernel_0  args(%arg18=%arg9, %arg19=%arg10, %arg20=%arg15, %arg21=%arg16, %arg22=%arg17) : index, index, memref<*xi8>, memref<*xi8>, memref<*xi32> {
        %c512 = arith.constant 512 : index
        %c8192 = arith.constant 8192 : index
        %c4096 = arith.constant 4096 : index
        %c65536 = arith.constant 65536 : index
        %c64 = arith.constant 64 : index
        %c1024 = arith.constant 1024 : index
        %c0_i32 = arith.constant 0 : i32
        %c0 = arith.constant 0 : index
        %c8 = arith.constant 8 : index
        %c1_0 = arith.constant 1 : index
        %c2 = arith.constant 2 : index
        %0 = arith.muli %arg19, %c64 : index
        %1 = arith.muli %arg18, %c65536 : index
        %alloc = memref.alloc() : memref<64x1024xi8, 1 : i32>
        %alloc_1 = memref.alloc() : memref<1024x64xi8, 1 : i32>
        %alloc_2 = memref.alloc() : memref<64x64xi32, 1>
        %alloc_3 = memref.alloc() : memref<8x8x8x8xi32, 2>
        scf.for %arg23 = %c0 to %c8 step %c1_0 {
          scf.for %arg24 = %c0 to %c8 step %c1_0 {
            %subview = memref.subview %alloc_3[%arg24, %arg23, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi32, 2> to memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>
            linalg.generic {indexing_maps = [#map, #map1], iterator_types = ["parallel", "parallel", "parallel", "parallel"]} ins(%c0_i32 : i32) outs(%subview : memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>) attrs =  {init_fill} {
            ^bb0(%in: i32, %out: i32):
              linalg.yield %in : i32
            }
          }
        }
        scf.for %arg23 = %c0 to %c1024 step %c64 {
          %4 = arith.addi %arg23, %1 : index
          air.dma_memcpy_nd (%alloc[%c0, %arg23] [%c64, %c64] [%c1024, %c1_0], %arg20[%c0, %4] [%c64, %c64] [%c1024, %c1_0]) {id = 1 : i32} : (memref<64x1024xi8, 1 : i32>, memref<*xi8>)
          air.dma_memcpy_nd (%alloc_1[%arg23, %c0] [%c64, %c64] [%c64, %c1_0], %arg21[%arg23, %0] [%c64, %c64] [%c64, %c1_0]) {id = 2 : i32} : (memref<1024x64xi8, 1 : i32>, memref<*xi8>)
          %alloc_4 = memref.alloc() : memref<8x8x8x8xi8, 2>
          air.dma_memcpy_nd (%alloc_4[] [] [], %alloc[%c0, %c0, %c0, %arg23] [%c8, %c8, %c8, %c8] [%c8, %c8192, %c1024, %c1_0]) : (memref<8x8x8x8xi8, 2>, memref<64x1024xi8, 1 : i32>)
          %alloc_5 = memref.alloc() : memref<8x8x8x8xi8, 2>
          air.dma_memcpy_nd (%alloc_5[] [] [], %alloc_1[%c0, %c0, %arg23, %c0] [%c8, %c8, %c8, %c8] [%c8, %c512, %c64, %c1_0]) : (memref<8x8x8x8xi8, 2>, memref<1024x64xi8, 1 : i32>)
          scf.for %arg24 = %c0 to %c8 step %c2 {
            scf.for %arg25 = %c0 to %c8 step %c2 {
              scf.for %arg26 = %c0 to %c8 step %c1_0 {
                %subview = memref.subview %alloc_4[%arg26, %arg24, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi8, 2> to memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>
                %subview_6 = memref.subview %alloc_5[%arg25, %arg26, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi8, 2> to memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>
                %subview_7 = memref.subview %alloc_3[%arg25, %arg24, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi32, 2> to memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>
                linalg.generic {indexing_maps = [#map2, #map3, #map4], iterator_types = ["parallel", "parallel", "reduction", "parallel", "parallel", "reduction"]} ins(%subview, %subview_6 : memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>, memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>) outs(%subview_7 : memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>) attrs =  {matmul_compute, packed_matmul} {
                ^bb0(%in: i8, %in_13: i8, %out: i32):
                  %11 = arith.extsi %in : i8 to i32
                  %12 = arith.extsi %in_13 : i8 to i32
                  %13 = arith.muli %11, %12 : i32
                  %14 = arith.addi %out, %13 : i32
                  linalg.yield %14 : i32
                }
                %5 = affine.apply #map5()[%arg25]
                %subview_8 = memref.subview %alloc_5[%5, %arg26, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi8, 2> to memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>
                %6 = affine.apply #map5()[%arg25]
                %subview_9 = memref.subview %alloc_3[%6, %arg24, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi32, 2> to memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>
                linalg.generic {indexing_maps = [#map2, #map3, #map4], iterator_types = ["parallel", "parallel", "reduction", "parallel", "parallel", "reduction"]} ins(%subview, %subview_8 : memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>, memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>) outs(%subview_9 : memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>) attrs =  {matmul_compute, packed_matmul} {
                ^bb0(%in: i8, %in_13: i8, %out: i32):
                  %11 = arith.extsi %in : i8 to i32
                  %12 = arith.extsi %in_13 : i8 to i32
                  %13 = arith.muli %11, %12 : i32
                  %14 = arith.addi %out, %13 : i32
                  linalg.yield %14 : i32
                }
                %7 = affine.apply #map5()[%arg24]
                %subview_10 = memref.subview %alloc_4[%arg26, %7, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi8, 2> to memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>
                %8 = affine.apply #map5()[%arg24]
                %subview_11 = memref.subview %alloc_3[%arg25, %8, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi32, 2> to memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>
                linalg.generic {indexing_maps = [#map2, #map3, #map4], iterator_types = ["parallel", "parallel", "reduction", "parallel", "parallel", "reduction"]} ins(%subview_10, %subview_6 : memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>, memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>) outs(%subview_11 : memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>) attrs =  {matmul_compute, packed_matmul} {
                ^bb0(%in: i8, %in_13: i8, %out: i32):
                  %11 = arith.extsi %in : i8 to i32
                  %12 = arith.extsi %in_13 : i8 to i32
                  %13 = arith.muli %11, %12 : i32
                  %14 = arith.addi %out, %13 : i32
                  linalg.yield %14 : i32
                }
                %9 = affine.apply #map5()[%arg25]
                %10 = affine.apply #map5()[%arg24]
                %subview_12 = memref.subview %alloc_3[%9, %10, 0, 0] [1, 1, 8, 8] [1, 1, 1, 1] : memref<8x8x8x8xi32, 2> to memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>
                linalg.generic {indexing_maps = [#map2, #map3, #map4], iterator_types = ["parallel", "parallel", "reduction", "parallel", "parallel", "reduction"]} ins(%subview_10, %subview_8 : memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>, memref<1x1x8x8xi8, strided<[512, 64, 8, 1], offset: ?>, 2>) outs(%subview_12 : memref<1x1x8x8xi32, strided<[512, 64, 8, 1], offset: ?>, 2>) attrs =  {matmul_compute, packed_matmul} {
                ^bb0(%in: i8, %in_13: i8, %out: i32):
                  %11 = arith.extsi %in : i8 to i32
                  %12 = arith.extsi %in_13 : i8 to i32
                  %13 = arith.muli %11, %12 : i32
                  %14 = arith.addi %out, %13 : i32
                  linalg.yield %14 : i32
                }
              }
            }
          }
          memref.dealloc %alloc_4 : memref<8x8x8x8xi8, 2>
          memref.dealloc %alloc_5 : memref<8x8x8x8xi8, 2>
        }
        air.dma_memcpy_nd (%alloc_2[] [] [], %alloc_3[%c0, %c0, %c0, %c0] [%c8, %c8, %c8, %c8] [%c64, %c8, %c512, %c1_0]) : (memref<64x64xi32, 1>, memref<8x8x8x8xi32, 2>)
        %2 = arith.muli %arg18, %c4096 : index
        %3 = arith.addi %2, %0 : index
        air.dma_memcpy_nd (%arg22[%c0, %3] [%c64, %c64] [%c64, %c1_0], %alloc_2[] [] []) {id = 3 : i32} : (memref<*xi32>, memref<64x64xi32, 1>)
        memref.dealloc %alloc_2 : memref<64x64xi32, 1>
        memref.dealloc %alloc_3 : memref<8x8x8x8xi32, 2>
      }
    }
    return
  }
}
