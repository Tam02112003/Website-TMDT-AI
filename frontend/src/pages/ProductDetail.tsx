import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { Product, Comment, CommentCreate } from '../lib/types';
import { formatPrice, formatDate } from '../lib/utils';
import { useAuth } from '../hooks/useAuth';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { 
  ShoppingCart, 
  Heart, 
  Share2, 
  Star, 
  Plus, 
  Minus,
  MessageCircle,
  ArrowLeft
} from 'lucide-react';

export function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const queryClient = useQueryClient();
  const [quantity, setQuantity] = useState(1);
  const [comment, setComment] = useState('');

  const { data: product, isLoading } = useQuery({
    queryKey: ['product', id],
    queryFn: async () => {
      const response = await api.get(`/products/${id}`);
      return response.data as Product;
    },
    enabled: !!id,
  });

  const { data: comments } = useQuery({
    queryKey: ['comments', id],
    queryFn: async () => {
      const response = await api.get(`/products/${id}/comments`);
      return response.data as Comment[];
    },
    enabled: !!id,
  });

  const { data: recommendations } = useQuery({
    queryKey: ['recommendations', id],
    queryFn: async () => {
      const response = await api.get(`/products/${id}/recommendations`);
      return response.data as Product[];
    },
    enabled: !!id,
  });

  const addToCartMutation = useMutation({
    mutationFn: async () => {
      await api.post('/cart/add', {
        product_id: parseInt(id!),
        quantity,
      });
    },
    onSuccess: () => {
      toast.success('Đã thêm vào giỏ hàng!');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Có lỗi xảy ra');
    },
  });

  const addCommentMutation = useMutation({
    mutationFn: async (commentData: CommentCreate) => {
      await api.post(`/products/${id}/comments`, commentData);
    },
    onSuccess: () => {
      toast.success('Đã thêm bình luận!');
      setComment('');
      queryClient.invalidateQueries({ queryKey: ['comments', id] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Có lỗi xảy ra');
    },
  });

  const handleAddToCart = () => {
    if (!isAuthenticated) {
      toast.error('Vui lòng đăng nhập để thêm vào giỏ hàng');
      navigate('/login');
      return;
    }
    addToCartMutation.mutate();
  };

  const handleAddComment = () => {
    if (!isAuthenticated) {
      toast.error('Vui lòng đăng nhập để bình luận');
      navigate('/login');
      return;
    }
    if (!comment.trim()) {
      toast.error('Vui lòng nhập nội dung bình luận');
      return;
    }
    addCommentMutation.mutate({
      product_id: parseInt(id!),
      content: comment,
      user_name: user?.username,
    });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Không tìm thấy sản phẩm</h2>
          <Button onClick={() => navigate('/products')}>
            Quay lại danh sách sản phẩm
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center space-x-2 text-sm text-gray-600 mb-6">
        <button
          onClick={() => navigate('/products')}
          className="flex items-center hover:text-primary-600 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Quay lại
        </button>
        <span>/</span>
        <span className="text-gray-900">{product.name}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
        {/* Product Image */}
        <div className="space-y-4">
          <div className="aspect-square bg-gray-100 rounded-xl overflow-hidden">
            {product.image_url ? (
              <img
                src={product.image_url}
                alt={product.name}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <ShoppingCart className="h-24 w-24 text-gray-400" />
              </div>
            )}
          </div>
        </div>

        {/* Product Info */}
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{product.name}</h1>
            <div className="flex items-center space-x-4 mb-4">
              <div className="flex items-center space-x-1">
                {[...Array(5)].map((_, i) => (
                  <Star
                    key={i}
                    className={`h-5 w-5 ${
                      i < 4 ? 'text-yellow-400 fill-current' : 'text-gray-300'
                    }`}
                  />
                ))}
                <span className="text-sm text-gray-600 ml-2">(4.5 - 123 đánh giá)</span>
              </div>
            </div>
            <p className="text-gray-600 text-lg">{product.description}</p>
          </div>

          <div className="border-t border-gray-200 pt-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-3xl font-bold text-primary-600">
                {formatPrice(product.price)}
              </span>
              <div className="flex items-center space-x-2">
                <button className="p-2 text-gray-400 hover:text-red-500 transition-colors">
                  <Heart className="h-6 w-6" />
                </button>
                <button className="p-2 text-gray-400 hover:text-primary-600 transition-colors">
                  <Share2 className="h-6 w-6" />
                </button>
              </div>
            </div>

            <div className="mb-6">
              <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                product.quantity > 10 
                  ? 'bg-green-100 text-green-800' 
                  : product.quantity > 0 
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-red-100 text-red-800'
              }`}>
                {product.quantity > 10 
                  ? `Còn ${product.quantity} sản phẩm` 
                  : product.quantity > 0 
                  ? `Chỉ còn ${product.quantity} sản phẩm`
                  : 'Hết hàng'
                }
              </span>
            </div>

            {product.quantity > 0 && (
              <div className="space-y-4">
                <div className="flex items-center space-x-4">
                  <span className="text-sm font-medium text-gray-700">Số lượng:</span>
                  <div className="flex items-center border border-gray-300 rounded-lg">
                    <button
                      onClick={() => setQuantity(Math.max(1, quantity - 1))}
                      className="p-2 hover:bg-gray-100 transition-colors"
                    >
                      <Minus className="h-4 w-4" />
                    </button>
                    <span className="px-4 py-2 border-x border-gray-300 min-w-[60px] text-center">
                      {quantity}
                    </span>
                    <button
                      onClick={() => setQuantity(Math.min(product.quantity, quantity + 1))}
                      className="p-2 hover:bg-gray-100 transition-colors"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="flex space-x-4">
                  <Button
                    onClick={handleAddToCart}
                    loading={addToCartMutation.isPending}
                    className="flex-1"
                  >
                    <ShoppingCart className="h-5 w-5 mr-2" />
                    Thêm vào giỏ hàng
                  </Button>
                  <Button variant="secondary" className="flex-1">
                    Mua ngay
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Comments Section */}
      <div className="border-t border-gray-200 pt-8 mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
          <MessageCircle className="h-6 w-6 mr-2" />
          Bình luận ({comments?.length || 0})
        </h2>

        {isAuthenticated && (
          <div className="bg-gray-50 rounded-lg p-6 mb-6">
            <div className="space-y-4">
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Viết bình luận của bạn..."
                rows={3}
                className="w-full rounded-lg border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
              <div className="flex justify-end">
                <Button
                  onClick={handleAddComment}
                  loading={addCommentMutation.isPending}
                  disabled={!comment.trim()}
                >
                  Gửi bình luận
                </Button>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-4">
          {comments?.map((comment) => (
            <div key={comment.id} className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-gray-900">
                  {comment.user_name || 'Người dùng ẩn danh'}
                </span>
                <span className="text-sm text-gray-500">
                  {formatDate(comment.created_at)}
                </span>
              </div>
              <p className="text-gray-700">{comment.content}</p>
            </div>
          ))}
          
          {comments?.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              Chưa có bình luận nào. Hãy là người đầu tiên bình luận!
            </div>
          )}
        </div>
      </div>

      {/* Recommendations */}
      {recommendations && recommendations.length > 0 && (
        <div className="border-t border-gray-200 pt-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Sản phẩm liên quan</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow duration-300"
              >
                <div className="aspect-square bg-gray-100 relative overflow-hidden">
                  {rec.image_url ? (
                    <img
                      src={rec.image_url}
                      alt={rec.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <ShoppingCart className="h-8 w-8 text-gray-400" />
                    </div>
                  )}
                </div>
                <div className="p-4">
                  <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                    {rec.name}
                  </h3>
                  <span className="text-lg font-bold text-primary-600">
                    {formatPrice(rec.price)}
                  </span>
                  <button
                    onClick={() => navigate(`/products/${rec.id}`)}
                    className="mt-3 w-full btn-primary"
                  >
                    Xem chi tiết
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}