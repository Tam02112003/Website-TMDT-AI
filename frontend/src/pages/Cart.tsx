import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { CartItem, Product } from '../lib/types';
import { formatPrice } from '../lib/utils';
import { useAuth } from '../hooks/useAuth';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Button } from '../components/ui/Button';
import { ShoppingCart, Plus, Minus, Trash2, ArrowRight } from 'lucide-react';

interface CartItemWithProduct extends CartItem {
  product?: Product;
}

export function Cart() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const { data: cartData, isLoading } = useQuery({
    queryKey: ['cart'],
    queryFn: async () => {
      const response = await api.get('/cart/');
      return response.data.cart as CartItem[];
    },
    enabled: isAuthenticated,
  });

  // Fetch product details for each cart item
  const { data: cartWithProducts } = useQuery({
    queryKey: ['cart-with-products', cartData],
    queryFn: async () => {
      if (!cartData || cartData.length === 0) return [];
      
      const cartWithProducts = await Promise.all(
        cartData.map(async (item) => {
          try {
            const response = await api.get(`/products/${item.product_id}`);
            return { ...item, product: response.data };
          } catch (error) {
            console.error(`Failed to fetch product ${item.product_id}:`, error);
            return item;
          }
        })
      );
      
      return cartWithProducts;
    },
    enabled: !!cartData && cartData.length > 0,
  });

  const updateQuantityMutation = useMutation({
    mutationFn: async ({ productId, quantity }: { productId: number; quantity: number }) => {
      await api.put('/cart/update', {
        product_id: productId,
        quantity,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cart'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Có lỗi xảy ra');
    },
  });

  const removeItemMutation = useMutation({
    mutationFn: async (productId: number) => {
      await api.delete(`/cart/remove?product_id=${productId}`);
    },
    onSuccess: () => {
      toast.success('Đã xóa sản phẩm khỏi giỏ hàng');
      queryClient.invalidateQueries({ queryKey: ['cart'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Có lỗi xảy ra');
    },
  });

  const handleUpdateQuantity = (productId: number, newQuantity: number) => {
    if (newQuantity < 1) return;
    updateQuantityMutation.mutate({ productId, quantity: newQuantity });
  };

  const handleRemoveItem = (productId: number) => {
    removeItemMutation.mutate(productId);
  };

  const handleCheckout = () => {
    if (!cartWithProducts || cartWithProducts.length === 0) {
      toast.error('Giỏ hàng trống');
      return;
    }
    navigate('/checkout');
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <ShoppingCart className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Vui lòng đăng nhập</h2>
          <p className="text-gray-600 mb-4">Bạn cần đăng nhập để xem giỏ hàng</p>
          <Button onClick={() => navigate('/login')}>
            Đăng nhập
          </Button>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const totalAmount = cartWithProducts?.reduce((total, item) => {
    return total + (item.product?.price || 0) * item.quantity;
  }, 0) || 0;

  const totalItems = cartWithProducts?.reduce((total, item) => total + item.quantity, 0) || 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Giỏ hàng</h1>
        <p className="text-gray-600">
          {totalItems > 0 ? `${totalItems} sản phẩm trong giỏ hàng` : 'Giỏ hàng trống'}
        </p>
      </div>

      {!cartWithProducts || cartWithProducts.length === 0 ? (
        <div className="text-center py-12">
          <ShoppingCart className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-medium text-gray-900 mb-2">Giỏ hàng trống</h3>
          <p className="text-gray-600 mb-6">Hãy thêm một số sản phẩm vào giỏ hàng của bạn</p>
          <Button onClick={() => navigate('/products')}>
            Tiếp tục mua sắm
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Cart Items */}
          <div className="lg:col-span-2 space-y-4">
            {cartWithProducts.map((item) => (
              <div
                key={item.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
              >
                <div className="flex items-center space-x-4">
                  <div className="w-20 h-20 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
                    {item.product?.image_url ? (
                      <img
                        src={item.product.image_url}
                        alt={item.product.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <ShoppingCart className="h-8 w-8 text-gray-400" />
                      </div>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-medium text-gray-900 truncate">
                      {item.product?.name || 'Sản phẩm không tồn tại'}
                    </h3>
                    <p className="text-sm text-gray-600 mt-1">
                      {item.product?.description}
                    </p>
                    <div className="flex items-center justify-between mt-4">
                      <span className="text-lg font-bold text-primary-600">
                        {item.product ? formatPrice(item.product.price) : 'N/A'}
                      </span>
                      
                      <div className="flex items-center space-x-3">
                        <div className="flex items-center border border-gray-300 rounded-lg">
                          <button
                            onClick={() => handleUpdateQuantity(item.product_id, item.quantity - 1)}
                            disabled={item.quantity <= 1 || updateQuantityMutation.isPending}
                            className="p-2 hover:bg-gray-100 transition-colors disabled:opacity-50"
                          >
                            <Minus className="h-4 w-4" />
                          </button>
                          <span className="px-4 py-2 border-x border-gray-300 min-w-[60px] text-center">
                            {item.quantity}
                          </span>
                          <button
                            onClick={() => handleUpdateQuantity(item.product_id, item.quantity + 1)}
                            disabled={updateQuantityMutation.isPending}
                            className="p-2 hover:bg-gray-100 transition-colors disabled:opacity-50"
                          >
                            <Plus className="h-4 w-4" />
                          </button>
                        </div>

                        <button
                          onClick={() => handleRemoveItem(item.product_id)}
                          disabled={removeItemMutation.isPending}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="h-5 w-5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Order Summary */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 sticky top-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Tóm tắt đơn hàng</h2>
              
              <div className="space-y-3 mb-6">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Tạm tính ({totalItems} sản phẩm)</span>
                  <span className="font-medium">{formatPrice(totalAmount)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Phí vận chuyển</span>
                  <span className="font-medium">Miễn phí</span>
                </div>
                <div className="border-t border-gray-200 pt-3">
                  <div className="flex justify-between">
                    <span className="text-lg font-semibold text-gray-900">Tổng cộng</span>
                    <span className="text-lg font-bold text-primary-600">
                      {formatPrice(totalAmount)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <Button
                  onClick={handleCheckout}
                  className="w-full"
                  disabled={totalAmount === 0}
                >
                  Thanh toán
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
                
                <Button
                  variant="secondary"
                  onClick={() => navigate('/products')}
                  className="w-full"
                >
                  Tiếp tục mua sắm
                </Button>
              </div>

              <div className="mt-6 text-center">
                <p className="text-xs text-gray-500">
                  Miễn phí vận chuyển cho đơn hàng trên 500.000đ
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}