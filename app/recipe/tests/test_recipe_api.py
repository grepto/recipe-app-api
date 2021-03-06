import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Ingredient, Tag

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer

RECIPES_URL = reverse('recipe:recipe-list')


def get_image_upload_url(recipe_id):
    """Return URL for recipe image upload"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


def get_detail_url(recipe_id):
    """Return recipe detail URL"""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def get_sample_ingredient(user, name='Cinnamon'):
    """Create and return sample ingredient"""
    return Ingredient.objects.create(user=user, name=name)


def get_sample_tag(user, name='Main course'):
    """Create and return sample tag"""
    return Tag.objects.create(user=user, name=name)


def get_sample_recipe(user, **params):
    """Create and return sample recipe"""
    defaults = {
        'title': 'Sample recipe',
        'time_minutes': 10,
        'price': 5.00,
    }
    defaults.update(params)

    return Recipe.objects.create(user=user, **defaults)


class PublicRecipeTestApi(TestCase):
    """Test unauthenticated recipe api access"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required"""
        res = self.client.get(RECIPES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeTestApi(TestCase):
    """Test authenticated recipe api access"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'test@test.com',
            'testpass',
        )

        self.client.force_authenticate(user=self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes"""
        get_sample_recipe(user=self.user)
        get_sample_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)
        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipes_limited_to_user(self):
        """Test retrieving recipes for user"""
        user2 = get_user_model().objects.create_user(
            'other@test.com',
            'testpass'
        )

        get_sample_recipe(user=user2)
        get_sample_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)
        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data, serializer.data)

    def test_view_recipe_detail(self):
        """Test recipe detail view"""
        recipe = get_sample_recipe(user=self.user)
        recipe.tags.add(get_sample_tag(user=self.user))
        recipe.ingredients.add(get_sample_ingredient(user=self.user))

        url = get_detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_basic_recipe(self):
        """Test creating recipe"""

        payload = {
            'title': "Chocolate cheesecake",
            'time_minutes': 30,
            'price': 20.00,
        }
        res = self.client.post(RECIPES_URL, payload)
        recipe = Recipe.objects.get(id=res.data['id'])

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        for key in payload.keys():
            self.assertEqual(payload[key], getattr(recipe, key))

    def test_create_recipe_with_tags(self):
        """Test creating recipe with tags"""
        tag1 = get_sample_tag(user=self.user, name='Vegan')
        tag2 = get_sample_tag(user=self.user, name='Desert')
        payload = {
            'title': 'Avocado lime cheesecake',
            'tags': [tag1.id, tag2.id],
            'time_minutes': 60,
            'price': 5.00,
        }
        res = self.client.post(RECIPES_URL, payload)
        recipe = Recipe.objects.get(id=res.data['id'])
        tags = recipe.tags.all()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(tags.count(), 2)
        self.assertIn(tag1, tags)
        self.assertIn(tag2, tags)

    def test_create_recipe_with_ingredients(self):
        """Test creating recipe with ingredients"""
        ingredient1 = get_sample_ingredient(user=self.user, name='Pprawns')
        ingredient2 = get_sample_ingredient(user=self.user, name='Ginger')
        payload = {
            'title': 'Thai prawn red curry',
            'ingredients': [ingredient1.id, ingredient2.id],
            'time_minutes': 80,
            'price': 85.00,
        }
        res = self.client.post(RECIPES_URL, payload)
        recipe = Recipe.objects.get(id=res.data['id'])
        ingredients = recipe.ingredients.all()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ingredients.count(), 2)
        self.assertIn(ingredient1, ingredients)
        self.assertIn(ingredient2, ingredients)

    def test_partial_update_recipe(self):
        """Test updating a recipe with patch"""
        recipe = get_sample_recipe(user=self.user)
        recipe.tags.add(get_sample_tag(user=self.user))
        new_tag = get_sample_tag(user=self.user, name='Molecular')

        payload = {'title': 'Mushed carbonara', 'tags': [new_tag.id]}
        url = get_detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()
        tags = recipe.tags.all()

        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(tags.count(), 1)
        self.assertIn(new_tag, tags)

    def test_full_update_recipe(self):
        """Test updating a recipe with put"""
        recipe = get_sample_recipe(user=self.user)
        recipe.tags.add(get_sample_tag(user=self.user))
        payload = {
            'title': 'Fish and chips',
            'time_minutes': 50,
            'price': 999.00,
        }
        url = get_detail_url(recipe.id)
        self.client.put(url, payload)

        recipe.refresh_from_db()
        tags = recipe.tags.all()

        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.time_minutes, payload['time_minutes'])
        self.assertEqual(recipe.price, payload['price'])
        self.assertEqual(tags.count(), 0)


class RecipeImageUploadTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'test@test.ru',
            'testpass'
        )
        self.client.force_authenticate(self.user)
        self.recipe = get_sample_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image_to_recipe(self):
        """Test uploading an image to recipe"""
        url = get_image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as ntf:
            img = Image.new('RGB', (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(url, {'image': ntf}, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading invalid image"""
        url = get_image_upload_url(self.recipe.id)
        res = self.client.post(url, {'image': 'noimage'}, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_recipes_by_tags(self):
        """Test returning recipes by specific tags"""
        recipe1 = get_sample_recipe(user=self.user, title='Vegan chicken')
        recipe2 = get_sample_recipe(user=self.user, title='Mashed potato')
        recipe3 = get_sample_recipe(user=self.user, title='Fish and chips')
        tag1 = get_sample_tag(user=self.user, name='Vegan')
        tag2 = get_sample_tag(user=self.user, name='Kids')
        recipe1.tags.add(tag1)
        recipe2.tags.add(tag2)

        res = self.client.get(
            RECIPES_URL,
            {'tags': f'{tag1.id},{tag2.id}'}
        )

        serializer1 = RecipeSerializer(recipe1)
        serializer2 = RecipeSerializer(recipe2)
        serializer3 = RecipeSerializer(recipe3)

        self.assertIn(serializer1.data, res.data)
        self.assertIn(serializer2.data, res.data)
        self.assertNotIn(serializer3.data, res.data)

    def test_filter_recipes_by_ingredients(self):
        """Test returning recipes by specific ingredients"""
        recipe1 = get_sample_recipe(user=self.user, title='Fried tomato')
        recipe2 = get_sample_recipe(user=self.user, title='Jelly chilly')
        recipe3 = get_sample_recipe(user=self.user, title='Candy lettuce')
        ingredient1 = get_sample_ingredient(user=self.user, name='Tomato')
        ingredient2 = get_sample_ingredient(user=self.user, name='Chilly')
        recipe1.ingredients.add(ingredient1)
        recipe2.ingredients.add(ingredient2)

        res = self.client.get(
            RECIPES_URL,
            {'ingredients': f'{ingredient1.id},{ingredient2.id}'}
        )

        seializer1 = RecipeSerializer(recipe1)
        seializer2 = RecipeSerializer(recipe2)
        seializer3 = RecipeSerializer(recipe3)

        self.assertIn(seializer1.data, res.data)
        self.assertIn(seializer2.data, res.data)
        self.assertNotIn(seializer3.data, res.data)
